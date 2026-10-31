"""Source-linked records. No destructive edits: every change appends a revision."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, case, func, literal, select, union_all, update
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.core.errors import ResourceNotFoundException
from app.core.time import utc_now
from app.models.clinical import Encounter, EncounterRevision, EncounterSource, FollowUpRevision, FollowUpTask
from app.models.document import MedicalDocument
from app.models.patient import Patient
from app.models.user import User
from app.schemas.clinical import (
    EncounterCreate, EncounterCorrect, EncounterOut, FollowUpCreate, FollowUpCorrect, FollowUpOut,
    TaskStatus, TimelineOut,
)
from app.services.audit_service import audit_service
from app.services.authorization import require_clinical_access, require_document_access

router = APIRouter(prefix="/clinical", tags=["Consultations and follow-ups"])
PageLimit = Query(default=50, ge=1, le=100)
PageOffset = Query(default=0, ge=0)


def authorize_patient(db, user, patient_id, request, write=False):
    require_clinical_access(db, user, patient_id, request, write=write)
    if not db.get(Patient, patient_id):
        raise ResourceNotFoundException("Patient")


def authorized_record(db, model, record_id, user, request, write=False):
    item = db.get(model, str(record_id))
    if not item:
        raise ResourceNotFoundException("Clinical record")
    require_clinical_access(db, user, item.patient_id, request, write=write)
    return item


def source_links(db, user, patient_id, ids, request):
    ids = sorted({str(i) for i in ids})
    documents = db.query(MedicalDocument).filter(
        MedicalDocument.id.in_(ids), MedicalDocument.patient_id == patient_id).all()
    if len(documents) != len(ids):
        raise HTTPException(422, "Every source must be an existing document owned by this patient")
    for doc in documents:
        require_document_access(db, user, doc, request)
    return [EncounterSource(document_id=i) for i in ids]


def actor_fields(user):
    return {"recorded_by": user.id,
            "provenance": "patient_reported" if user.role == "patient" else "clinician_recorded"}


def record_write(db, user, item, revision, action, resource):
    db.add(revision)
    audit_service.log_event(db, action, resource, actor_id=user.id, patient_id=item.patient_id,
                            resource_id=item.id, details=f"version={revision.version}", commit=False)
    db.commit()


def advance_version(db, model, item, expected):
    result = db.execute(update(model).where(model.id == item.id, model.version == expected)
                        .values(version=expected + 1, updated_at=utc_now())
                        .execution_options(synchronize_session=False))
    if result.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Record changed. Reload the latest version before saving your correction.")


def encounter_out(db, item, revision):
    return dict(id=item.id, patient_id=item.patient_id, created_by=item.created_by,
                version=revision.version, occurred_on=revision.occurred_on, title=revision.title,
                notes=revision.notes, recorded_by=revision.recorded_by,
                recorded_by_name=db.get(User, revision.recorded_by).full_name,
                provenance=revision.provenance, correction_reason=revision.correction_reason,
                recorded_at=revision.created_at, created_at=item.created_at,
                sources=[{"id": s.document_id, "title": s.document.title, "file_name": s.document.file_name}
                         for s in revision.sources])


def follow_up_out(db, item, revision):
    return dict(id=item.id, patient_id=item.patient_id, encounter_id=item.encounter_id,
                created_by=item.created_by, version=revision.version, title=revision.title,
                due_on=revision.due_on, status=revision.status, outcome=revision.outcome,
                overdue=revision.status == "pending" and revision.due_on < utc_now().date(),
                recorded_by=revision.recorded_by, recorded_by_name=db.get(User, revision.recorded_by).full_name,
                provenance=revision.provenance, correction_reason=revision.correction_reason,
                recorded_at=revision.created_at, created_at=item.created_at)


def log_read(db, user, patient_id, resource, resource_id=None):
    audit_service.log_event(db, "VIEW_RECORD", resource, actor_id=user.id,
                            patient_id=patient_id, resource_id=resource_id)


@router.post("/encounters", response_model=EncounterOut, status_code=201)
def create_encounter(payload: EncounterCreate, request: Request,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    patient_id = str(payload.patient_id)
    authorize_patient(db, user, patient_id, request, write=True)
    links = source_links(db, user, patient_id, payload.source_document_ids, request)
    item = Encounter(patient_id=patient_id, created_by=user.id)
    db.add(item)
    db.flush()
    revision = EncounterRevision(encounter_id=item.id, version=1, occurred_on=payload.occurred_on,
                                 title=payload.title, notes=payload.notes, sources=links,
                                 correction_reason="Initial record", **actor_fields(user))
    record_write(db, user, item, revision, "CREATE_ENCOUNTER", "encounter")
    return encounter_out(db, item, revision)


@router.get("/encounters", response_model=list[EncounterOut])
def list_encounters(patient_id: UUID, request: Request, limit: int = PageLimit, offset: int = PageOffset,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = str(patient_id)
    authorize_patient(db, user, target, request)
    rows = db.query(Encounter, EncounterRevision).join(EncounterRevision, and_(
        EncounterRevision.encounter_id == Encounter.id, EncounterRevision.version == Encounter.version))
    rows = rows.filter(Encounter.patient_id == target).order_by(
        EncounterRevision.occurred_on.desc(), Encounter.id).offset(offset).limit(limit).all()
    result = [encounter_out(db, item, revision) for item, revision in rows]
    log_read(db, user, target, "encounter_list")
    return result


@router.get("/encounters/{encounter_id}", response_model=EncounterOut)
def get_encounter(encounter_id: UUID, request: Request,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = authorized_record(db, Encounter, encounter_id, user, request)
    revision = db.query(EncounterRevision).filter_by(encounter_id=item.id, version=item.version).one()
    result = encounter_out(db, item, revision)
    log_read(db, user, item.patient_id, "encounter", item.id)
    return result


@router.put("/encounters/{encounter_id}", response_model=EncounterOut)
def correct_encounter(encounter_id: UUID, payload: EncounterCorrect, request: Request,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = authorized_record(db, Encounter, encounter_id, user, request, write=True)
    links = source_links(db, user, item.patient_id, payload.source_document_ids, request)
    advance_version(db, Encounter, item, payload.expected_version)
    revision = EncounterRevision(encounter_id=item.id, version=payload.expected_version + 1,
                                 occurred_on=payload.occurred_on, title=payload.title, notes=payload.notes,
                                 sources=links, correction_reason=payload.correction_reason, **actor_fields(user))
    record_write(db, user, item, revision, "CORRECT_ENCOUNTER", "encounter")
    return encounter_out(db, item, revision)


@router.get("/encounters/{encounter_id}/history", response_model=list[EncounterOut])
def encounter_history(encounter_id: UUID, request: Request, limit: int = PageLimit, offset: int = PageOffset,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = authorized_record(db, Encounter, encounter_id, user, request)
    revisions = db.query(EncounterRevision).filter_by(encounter_id=item.id).order_by(
        EncounterRevision.version.desc()).offset(offset).limit(limit).all()
    result = [encounter_out(db, item, revision) for revision in revisions]
    log_read(db, user, item.patient_id, "encounter_history", item.id)
    return result


@router.post("/follow-ups", response_model=FollowUpOut, status_code=201)
def create_follow_up(payload: FollowUpCreate, request: Request,
                     user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    encounter = authorized_record(db, Encounter, payload.encounter_id, user, request, write=True)
    item = FollowUpTask(patient_id=encounter.patient_id, encounter_id=encounter.id, created_by=user.id)
    db.add(item)
    db.flush()
    revision = FollowUpRevision(task_id=item.id, version=1,
                                **payload.model_dump(exclude={"encounter_id"}),
                                correction_reason="Initial record", **actor_fields(user))
    record_write(db, user, item, revision, "CREATE_FOLLOW_UP", "follow_up")
    return follow_up_out(db, item, revision)


@router.get("/follow-ups", response_model=list[FollowUpOut])
def list_follow_ups(patient_id: UUID, request: Request, status: TaskStatus | None = None,
                    limit: int = PageLimit, offset: int = PageOffset,
                    user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = str(patient_id)
    authorize_patient(db, user, target, request)
    rows = db.query(FollowUpTask, FollowUpRevision).join(FollowUpRevision, and_(
        FollowUpRevision.task_id == FollowUpTask.id, FollowUpRevision.version == FollowUpTask.version)
    ).filter(FollowUpTask.patient_id == target)
    if status:
        rows = rows.filter(FollowUpRevision.status == status)
    rows = rows.order_by(FollowUpRevision.due_on, FollowUpTask.id).offset(offset).limit(limit).all()
    result = [follow_up_out(db, item, revision) for item, revision in rows]
    log_read(db, user, target, "follow_up_list")
    return result


@router.get("/follow-ups/{task_id}", response_model=FollowUpOut)
def get_follow_up(task_id: UUID, request: Request,
                  user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = authorized_record(db, FollowUpTask, task_id, user, request)
    revision = db.query(FollowUpRevision).filter_by(task_id=item.id, version=item.version).one()
    result = follow_up_out(db, item, revision)
    log_read(db, user, item.patient_id, "follow_up", item.id)
    return result


@router.put("/follow-ups/{task_id}", response_model=FollowUpOut)
def correct_follow_up(task_id: UUID, payload: FollowUpCorrect, request: Request,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = authorized_record(db, FollowUpTask, task_id, user, request, write=True)
    advance_version(db, FollowUpTask, item, payload.expected_version)
    revision = FollowUpRevision(task_id=item.id, version=payload.expected_version + 1,
                                **payload.model_dump(exclude={"expected_version"}), **actor_fields(user))
    record_write(db, user, item, revision, "UPDATE_FOLLOW_UP", "follow_up")
    return follow_up_out(db, item, revision)


@router.get("/follow-ups/{task_id}/history", response_model=list[FollowUpOut])
def follow_up_history(task_id: UUID, request: Request, limit: int = PageLimit, offset: int = PageOffset,
                      user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    item = authorized_record(db, FollowUpTask, task_id, user, request)
    revisions = db.query(FollowUpRevision).filter_by(task_id=item.id).order_by(
        FollowUpRevision.version.desc()).offset(offset).limit(limit).all()
    result = [follow_up_out(db, item, revision) for revision in revisions]
    log_read(db, user, item.patient_id, "follow_up_history", item.id)
    return result


@router.get("/timeline", response_model=list[TimelineOut])
def timeline(patient_id: UUID, request: Request, kind: Literal["document", "encounter"] | None = None,
             search: str = Query(default="", max_length=100), limit: int = PageLimit, offset: int = PageOffset,
             user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    target = str(patient_id)
    authorize_patient(db, user, target, request)
    documents = select(
        MedicalDocument.id.label("id"), literal("document").label("kind"),
        func.coalesce(func.date(MedicalDocument.clinical_date), func.date(MedicalDocument.created_at)).label("event_date"),
        case((MedicalDocument.clinical_date.is_not(None), "clinical_date"), else_="upload_date").label("date_basis"),
        MedicalDocument.title.label("title"), literal("source_unverified").label("provenance"),
    ).where(MedicalDocument.patient_id == target)
    encounters = select(
        Encounter.id.label("id"), literal("encounter").label("kind"),
        func.date(EncounterRevision.occurred_on).label("event_date"),
        literal("consultation_date").label("date_basis"), EncounterRevision.title.label("title"),
        EncounterRevision.provenance.label("provenance"),
    ).join(EncounterRevision, and_(EncounterRevision.encounter_id == Encounter.id,
                                   EncounterRevision.version == Encounter.version)
    ).where(Encounter.patient_id == target)
    combined = union_all(documents, encounters).subquery()
    query = select(combined)
    if kind:
        query = query.where(combined.c.kind == kind)
    if search.strip():
        query = query.where(combined.c.title.icontains(search.strip(), autoescape=True))
    result = db.execute(query.order_by(combined.c.event_date.desc(), combined.c.kind, combined.c.id)
                        .offset(offset).limit(limit)).mappings().all()
    log_read(db, user, target, "clinical_timeline")
    return result
