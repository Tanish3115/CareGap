from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.api.clinical import authorize_patient, authorized_record, advance_version
from app.models.health_record import HealthRecord, HealthRevision
from app.models.interoperability import FHIRImportLink
from app.models.user import User
from app.schemas.health_record import Kind, RecordCreate, RecordCorrect, RecordOut
from app.services.health_records import current_records, record_out, sources, validate_actor, validate_target
from app.services.audit_service import audit_service
from app.core.clinical_resources import KIND_RESOURCE
from app.services.authorization import allowed_clinical_resources

router = APIRouter(prefix="/clinical/records", tags=["Structured clinical records"])


def rescheduling_actor(user, payload, previous=None):
    if user.role != "patient" or payload.data.kind not in ("appointment", "referral", "test"):
        return
    fields = (
        "reschedule_requested_for",
        "reschedule_reason",
        "reschedule_decision",
        "reschedule_review_note",
    )
    data = payload.data.model_dump(mode="json")
    if data.get("reschedule_decision") in ("approved", "declined") and (
        not previous or any(data.get(key) != previous.get(key) for key in fields)
    ):
        raise HTTPException(403, "Only a consented clinician may approve or decline a rescheduling request")


def save(db, user, root, payload, version, request):
    links = sources(db, user, root.patient_id, payload.source_document_ids, request)
    validate_target(db, user, root.patient_id, payload.data)
    revision = HealthRevision(
        record_id=root.id,
        version=version,
        title=payload.title,
        occurred_on=payload.occurred_on,
        data=payload.data.model_dump(mode="json"),
        recorded_by=user.id,
        provenance="patient_reported" if user.role == "patient" else "clinician_recorded",
        reason=payload.reason,
        sources=links,
    )
    db.add(revision)
    if version > 1:
        previous = db.query(HealthRevision).filter_by(record_id=root.id, version=version - 1).one()
        imported = db.get(FHIRImportLink, previous.id)
        if imported:
            db.flush()
            db.add(FHIRImportLink(revision_id=revision.id, import_id=imported.import_id))
    audit_service.log_event(
        db,
        "SAVE_STRUCTURED_RECORD",
        root.kind,
        actor_id=user.id,
        patient_id=root.patient_id,
        resource_id=root.id,
        details=f"version={version}",
        commit=False,
    )
    db.commit()
    return record_out(db, root, revision)


@router.post("", response_model=RecordOut, status_code=201)
def create_record(
    payload: RecordCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(payload.patient_id)
    authorize_patient(db, user, target, request, write=True, resource=KIND_RESOURCE[payload.data.kind])
    validate_actor(user, payload.data.kind)
    rescheduling_actor(user, payload)
    sources(db, user, target, payload.source_document_ids, request)
    validate_target(db, user, target, payload.data)
    root = HealthRecord(patient_id=target, kind=payload.data.kind)
    db.add(root)
    db.flush()
    return save(db, user, root, payload, 1, request)


@router.get("", response_model=list[RecordOut])
def list_records(
    patient_id: UUID,
    request: Request,
    kind: Kind | None = None,
    care_only: bool = False,
    search: str = Query("", max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    authorize_patient(
        db, user, target, request, resource=KIND_RESOURCE[kind] if kind else None, any_resource=kind is None
    )
    allowed = allowed_clinical_resources(db, user, target)
    query = current_records(db, target)
    query = query.filter(
        HealthRecord.kind.in_([key for key, group in KIND_RESOURCE.items() if group in allowed])
    )
    if kind:
        query = query.filter(HealthRecord.kind == kind)
    if care_only:
        query = query.filter(HealthRecord.kind.in_(("appointment", "referral", "test")))
    if search.strip():
        query = query.filter(HealthRevision.title.contains(search.strip(), autoescape=True))
    rows = (
        query.order_by(HealthRevision.occurred_on.desc(), HealthRecord.id).offset(offset).limit(limit).all()
    )
    result = [record_out(db, root, revision) for root, revision in rows]
    audit_service.log_event(
        db, "VIEW_STRUCTURED_RECORDS", "clinical_records", actor_id=user.id, patient_id=target
    )
    return result


@router.get("/{record_id}", response_model=RecordOut)
def get_record(
    record_id: UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    root = authorized_record(db, HealthRecord, record_id, user, request)
    revision = db.query(HealthRevision).filter_by(record_id=root.id, version=root.version).one()
    result = record_out(db, root, revision)
    audit_service.log_event(
        db,
        "VIEW_STRUCTURED_RECORD",
        root.kind,
        actor_id=user.id,
        patient_id=root.patient_id,
        resource_id=root.id,
    )
    return result


@router.put("/{record_id}", response_model=RecordOut)
def correct_record(
    record_id: UUID,
    payload: RecordCorrect,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    root = authorized_record(db, HealthRecord, record_id, user, request, write=True)
    validate_actor(user, root.kind)
    previous = db.query(HealthRevision).filter_by(record_id=root.id, version=root.version).one()
    rescheduling_actor(user, payload, previous.data)
    if payload.data.kind != root.kind:
        raise HTTPException(422, "The clinical resource kind cannot be changed")
    # Validate sources before CAS so input failures cannot leave a partial revision.
    sources(db, user, root.patient_id, payload.source_document_ids, request)
    validate_target(db, user, root.patient_id, payload.data)
    advance_version(db, HealthRecord, root, payload.expected_version)
    return save(db, user, root, payload, payload.expected_version + 1, request)


@router.get("/{record_id}/history", response_model=list[RecordOut])
def history(
    record_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    root = authorized_record(db, HealthRecord, record_id, user, request)
    rows = (
        db.query(HealthRevision)
        .filter_by(record_id=root.id)
        .order_by(HealthRevision.version.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [record_out(db, root, revision) for revision in rows]
    audit_service.log_event(
        db,
        "VIEW_STRUCTURED_HISTORY",
        root.kind,
        actor_id=user.id,
        patient_id=root.patient_id,
        resource_id=root.id,
    )
    return result
