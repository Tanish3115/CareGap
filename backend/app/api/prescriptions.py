from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import and_, func, update
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.api.document_reviews import review_access
from app.core.errors import PermissionDeniedException, ResourceNotFoundException
from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.models.patient import Patient
from app.models.prescription import MedicationEntry, PrescriptionRevision
from app.models.user import User
from app.schemas.prescription import (
    CORE_FIELDS,
    FIELD_NAMES,
    GeneratePrescription,
    MedicationEntryOut,
    PrescriptionItem,
    PrescriptionContext,
    PrescriptionOut,
    SavePrescription,
)
from app.services.authorization import (
    allowed_clinical_resources,
    require_clinical_access,
    require_document_access,
)
from app.services.audit_service import audit_service
from app.services.prescription_extraction import (
    extract_explicit_lines,
    extract_context,
    validate_context,
    missing_fields,
    validate_items,
)
from app.services.storage_service import storage_service
from app.services.medication_terminology import load_catalog, propose
from app.schemas.prescription import StrictInput
from pydantic import Field

router = APIRouter(tags=["Source-bound prescriptions"])


class TerminologyInput(StrictInput):
    source_review_version: int = Field(ge=1)
    items: list[PrescriptionItem] = Field(max_length=50)


@router.post("/documents/{document_id}/prescription/terminology")
def terminology_candidates(
    document_id: UUID,
    payload: TerminologyInput,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = prescription_access(db, user, document_id, request, write=True)
    source = (
        db.query(DocumentReviewRevision)
        .filter_by(document_id=doc.id, version=payload.source_review_version)
        .first()
    )
    if not source or doc.review_version != source.version or source.source_sha256 != doc.sha256_hash:
        raise HTTPException(
            409, "Source review changed or is missing. Rebuild from the current transcription."
        )
    validate_items(payload.items, source.reviewed_text)
    catalog = load_catalog()
    result = [
        propose(item.name.value, catalog) if item.name else dict(state="unmatched", candidates=[])
        for item in payload.items
    ]
    audit_service.log_event(
        db,
        "LOOKUP_MEDICATION_TERMINOLOGY",
        "document",
        actor_id=user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
    )
    return dict(
        mode=catalog[0] if catalog else "disabled",
        rows=result,
        requires_clinician_review=True,
        clinical_safety_checked=False,
    )


def can_edit(db, user, patient_id):
    return {"medications", "source_reviews"} <= allowed_clinical_resources(db, user, patient_id, write=True)


def prescription_access(db, user, document_id, request, write=False):
    doc = review_access(db, user, document_id, request, write=write)
    require_clinical_access(db, user, doc.patient_id, request, write=write, resource="medications")
    if doc.document_type != "prescription":
        raise HTTPException(422, "Structured prescription drafts require a prescription document")
    return doc


def repeated_names(items):
    names = [item.name.value.casefold() for item in items if item.name]
    return {name for name in names if names.count(name) > 1}


def out(db, doc, revision, user):
    source = db.get(DocumentReviewRevision, revision.source_review_id)
    items = [PrescriptionItem.model_validate(item) for item in revision.items]
    return dict(
        id=revision.id,
        document_id=doc.id,
        patient_id=doc.patient_id,
        version=revision.version,
        source_review_version=source.version,
        source_text=source.reviewed_text,
        source_sha256=source.source_sha256,
        source_stale=source.version != doc.review_version,
        state=revision.state,
        items=items,
        context=revision.context or {},
        missing_fields=[missing_fields(item) for item in items],
        extractor_version=revision.extractor_version,
        author_name=db.get(User, revision.author_id).full_name,
        author_role=revision.author_role,
        reason=revision.reason,
        created_at=revision.created_at,
        can_edit=can_edit(db, user, doc.patient_id),
        can_confirm=user.role == "doctor" and can_edit(db, user, doc.patient_id),
    )


def save_revision(
    db,
    doc,
    user,
    expected,
    source_version,
    items,
    reason,
    confirm=False,
    acknowledge=False,
    extractor="human-source-bound-v2",
    context=None,
):
    if confirm and user.role != "doctor":
        raise PermissionDeniedException(
            "Only a verified clinician with explicit clinical write consent can confirm prescription transcriptions"
        )
    source = db.query(DocumentReviewRevision).filter_by(document_id=doc.id, version=source_version).first()
    if not source or doc.review_version != source_version or source.source_sha256 != doc.sha256_hash:
        raise HTTPException(
            409, "Source review changed or is missing. Rebuild from the current transcription."
        )
    context = context or PrescriptionContext()
    validate_items(items, source.reviewed_text, confirm, acknowledge)
    validate_context(context, source.reviewed_text, confirm)
    duplicates = repeated_names(items)
    if confirm and duplicates and not acknowledge:
        raise HTTPException(422, "Acknowledge repeated source names and compare their source passages")
    with storage_service.materialize(doc.file_path, doc.sha256_hash, doc.storage_backend):
        pass
    changed = db.execute(
        update(MedicalDocument)
        .where(
            MedicalDocument.id == doc.id,
            MedicalDocument.prescription_version == expected,
            MedicalDocument.review_version == source_version,
        )
        .values(prescription_version=expected + 1)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Draft or source changed. Reload before saving.")
    revision = PrescriptionRevision(
        document_id=doc.id,
        source_review_id=source.id,
        version=expected + 1,
        state="clinician_confirmed" if confirm else "draft",
        context=context.model_dump(),
        items=[item.model_dump() for item in items],
        extractor_version=extractor,
        author_id=user.id,
        author_role=user.role,
        reason=reason,
    )
    db.add(revision)
    db.flush()
    if confirm:
        for index, item in enumerate(items):
            values = {
                field: getattr(item, field).value if getattr(item, field) else None for field in FIELD_NAMES
            }
            db.add(
                MedicationEntry(
                    patient_id=doc.patient_id,
                    document_id=doc.id,
                    prescription_revision_id=revision.id,
                    row_number=index,
                    **values,
                    evidence=item.model_dump(),
                    needs_clarification=(
                        any(getattr(item, field) is None for field in CORE_FIELDS)
                        or item.name.value.casefold() in duplicates
                    ),
                )
            )
    audit_service.log_event(
        db,
        "CONFIRM_PRESCRIPTION_TEXT" if confirm else "SAVE_PRESCRIPTION_DRAFT",
        "document",
        actor_id=user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
        details=f"version={revision.version}",
        commit=False,
    )
    db.commit()
    return out(db, doc, revision, user)


@router.get("/documents/{document_id}/prescription", response_model=PrescriptionOut | None)
def get_prescription(
    document_id: UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    doc = prescription_access(db, user, document_id, request)
    revision = (
        db.query(PrescriptionRevision).filter_by(document_id=doc.id, version=doc.prescription_version).first()
    )
    result = out(db, doc, revision, user) if revision else None
    audit_service.log_event(
        db,
        "VIEW_PRESCRIPTION_DRAFT",
        "document",
        actor_id=user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
    )
    return result


@router.post(
    "/documents/{document_id}/prescription/generate", response_model=PrescriptionOut, status_code=201
)
def generate_prescription(
    document_id: UUID,
    payload: GeneratePrescription,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = prescription_access(db, user, document_id, request, write=True)
    source = (
        db.query(DocumentReviewRevision)
        .filter_by(document_id=doc.id, version=payload.source_review_version)
        .first()
    )
    if not source:
        raise HTTPException(409, "Save a current source transcription review before generating a draft")
    return save_revision(
        db,
        doc,
        user,
        payload.expected_version,
        payload.source_review_version,
        extract_explicit_lines(source.reviewed_text),
        "Generated candidates from explicit labels in reviewed transcription",
        extractor="explicit-labels-v2",
        context=extract_context(source.reviewed_text),
    )


@router.post("/documents/{document_id}/prescription", response_model=PrescriptionOut, status_code=201)
def save_prescription(
    document_id: UUID,
    payload: SavePrescription,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = prescription_access(db, user, document_id, request, write=True)
    return save_revision(
        db,
        doc,
        user,
        payload.expected_version,
        payload.source_review_version,
        payload.items,
        payload.reason,
        payload.confirm,
        payload.missing_fields_acknowledged,
        context=payload.context,
    )


@router.get("/documents/{document_id}/prescription/history", response_model=list[PrescriptionOut])
def prescription_history(
    document_id: UUID,
    request: Request,
    limit: int = Query(default=10, ge=1, le=30),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = prescription_access(db, user, document_id, request)
    rows = (
        db.query(PrescriptionRevision)
        .filter_by(document_id=doc.id)
        .order_by(PrescriptionRevision.version.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [out(db, doc, row, user) for row in rows]
    audit_service.log_event(
        db,
        "VIEW_PRESCRIPTION_HISTORY",
        "document",
        actor_id=user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
    )
    return result


@router.get("/medications", response_model=list[MedicationEntryOut])
def list_medications(
    patient_id: UUID,
    request: Request,
    document_id: UUID | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    require_clinical_access(db, user, target, request, resource="medications")
    if not db.get(Patient, target):
        raise ResourceNotFoundException("Patient")
    latest = (
        db.query(PrescriptionRevision.document_id, func.max(PrescriptionRevision.version).label("version"))
        .filter(PrescriptionRevision.state == "clinician_confirmed")
        .group_by(PrescriptionRevision.document_id)
        .subquery()
    )
    rows = (
        db.query(MedicationEntry, PrescriptionRevision, MedicalDocument, DocumentReviewRevision)
        .join(PrescriptionRevision, PrescriptionRevision.id == MedicationEntry.prescription_revision_id)
        .join(
            latest,
            and_(
                latest.c.document_id == PrescriptionRevision.document_id,
                latest.c.version == PrescriptionRevision.version,
            ),
        )
        .join(MedicalDocument, MedicalDocument.id == MedicationEntry.document_id)
        .join(DocumentReviewRevision, DocumentReviewRevision.id == PrescriptionRevision.source_review_id)
        .filter(MedicationEntry.patient_id == target)
    )
    if document_id:
        rows = rows.filter(MedicationEntry.document_id == str(document_id))
    result = []
    for entry, revision, doc, source in (
        rows.order_by(MedicationEntry.created_at.desc(), MedicationEntry.id).offset(offset).limit(limit)
    ):
        require_document_access(db, user, doc, request)
        item = PrescriptionItem.model_validate(entry.evidence)
        result.append(
            dict(
                id=entry.id,
                patient_id=target,
                document_id=doc.id,
                prescription_version=revision.version,
                **{field: getattr(entry, field) for field in FIELD_NAMES},
                needs_clarification=entry.needs_clarification,
                missing_fields=missing_fields(item),
                source_stale=source.version != doc.review_version,
                draft_pending=doc.prescription_version > revision.version,
                evidence=item,
                confirmed_by_name=db.get(User, revision.author_id).full_name,
                created_at=entry.created_at,
                coding=item.coding,
            )
        )
    audit_service.log_event(
        db, "VIEW_DOCUMENTED_MEDICATIONS", "medication_list", actor_id=user.id, patient_id=target
    )
    return result
