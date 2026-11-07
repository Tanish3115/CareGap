"""Patient-owned deletion; clinical evidence dependencies never disappear silently."""

import hashlib
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.core.errors import PermissionDeniedException, ResourceNotFoundException
from app.models.user import User
from app.models.document import MedicalDocument
from app.models.processing import DocumentProcessingJob
from app.models.document_review import DocumentReviewRevision
from app.models.prescription import MedicationEntry, PrescriptionRevision
from app.models.file_deletion import FileDeletion
from app.models.clinical import Encounter, EncounterSource, FollowUpTask, FollowUpRevision
from app.models.health_record import HealthRecord, HealthRevision, HealthSource
from app.models.interoperability import FHIRImportLink
from app.models.coordination import NotificationDelivery
from app.models.medication_use import MedicationUse, MedicationUseRevision, MedicationReconciliation
from app.services.audit_service import audit_service

router = APIRouter(tags=["Patient-owned deletion"])


@router.get("/patient-file-deletions")
def file_deletion_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != "patient" or not user.patient_profile:
        raise PermissionDeniedException("Only patients can view their file cleanup status")
    rows = (
        db.query(FileDeletion)
        .filter_by(patient_id=user.patient_profile.id)
        .order_by(FileDeletion.created_at.desc(), FileDeletion.id.desc())
        .limit(50)
        .all()
    )
    return [
        dict(
            document_id=row.document_id,
            status=row.status,
            attempts=row.attempts,
            retry_required=bool(row.error_code),
            created_at=row.created_at,
        )
        for row in rows
    ]


def owned(db, user, model, record_id):
    if user.role != "patient":
        raise PermissionDeniedException("Only the patient owner can delete this record")
    item = db.get(model, str(record_id))
    if item is None:
        raise ResourceNotFoundException("Record")
    if not user.patient_profile or item.patient_id != user.patient_profile.id:
        raise PermissionDeniedException("Cannot delete another patient's record")
    return item


def lock(db, model, item, expected):
    changed = db.execute(
        update(model)
        .where(model.id == item.id, model.version == expected)
        .values(version=model.version)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Record changed. Reload before confirming deletion.")


def finish(db, user, item, resource):
    audit_service.log_event(
        db,
        "DELETE_" + resource.upper(),
        resource,
        actor_id=user.id,
        patient_id=item.patient_id,
        resource_id=item.id,
        commit=False,
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "Record is referenced by other records. Review those links before deleting."
        ) from None


def remove(db, model, condition):
    db.execute(delete(model).where(condition).execution_options(synchronize_session=False))


def document_state(db, item):
    job = db.query(DocumentProcessingJob).filter_by(document_id=item.id).first()
    links = (
        db.query(EncounterSource).filter_by(document_id=item.id).count()
        + db.query(HealthSource).filter_by(document_id=item.id).count()
    )
    entries = db.query(MedicationEntry).filter_by(document_id=item.id).count()
    if (
        db.query(MedicationEntry)
        .filter(MedicationEntry.document_id == item.id, MedicationEntry.patient_id != item.patient_id)
        .first()
    ):
        return dict(
            token="0" * 64, allowed=False, reason="Source storage requires operator review before deletion."
        )
    entry_ids = select(MedicationEntry.id).where(MedicationEntry.document_id == item.id)
    reports = (
        db.query(MedicationUseRevision).filter(MedicationUseRevision.source_entry_id.in_(entry_ids)).count()
    )
    reason = (
        "Document is linked to clinical records or medication reports. Remove dependent records or use the reviewed privacy workflow."
        if links or reports
        else "Document processing is active. Try again when processing finishes."
        if job and job.status == "processing"
        else ""
    )
    value = [
        item.id,
        item.sha256_hash,
        item.review_version,
        item.prescription_version,
        str(item.updated_at),
        [job.status, job.attempts] if job else None,
        links,
        entries,
        reports,
    ]
    return dict(
        token=hashlib.sha256(json.dumps(value).encode()).hexdigest(), allowed=not reason, reason=reason
    )


@router.get("/documents/{record_id}/deletion-preview")
def document_preview(record_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return document_state(db, owned(db, user, MedicalDocument, record_id))


@router.delete("/documents/{record_id}", status_code=202)
def delete_document(
    record_id: UUID,
    expected_token: str = Query(min_length=64, max_length=64),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = owned(db, user, MedicalDocument, record_id)
    changed = db.execute(
        update(MedicalDocument)
        .where(MedicalDocument.id == item.id, MedicalDocument.updated_at == item.updated_at)
        .values(updated_at=MedicalDocument.updated_at)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise HTTPException(409, "Document changed. Reload before confirming deletion.")
    db.refresh(item)
    # Serialize deletion against claim/finish/retry of the processing job.
    job = db.query(DocumentProcessingJob).filter_by(document_id=item.id).with_for_update().first()
    state = document_state(db, item)
    if not state["allowed"]:
        raise HTTPException(409, state["reason"])
    if state["token"] != expected_token:
        raise HTTPException(409, "Document changed. Reload before confirming deletion.")
    if (
        not item.file_path.startswith(item.patient_id + "/")
        or db.query(MedicalDocument)
        .filter(
            MedicalDocument.file_path == item.file_path,
            MedicalDocument.storage_backend == item.storage_backend,
            MedicalDocument.id != item.id,
        )
        .first()
    ):
        raise HTTPException(409, "Source storage requires operator review before deletion.")
    db.add(
        FileDeletion(
            patient_id=item.patient_id,
            document_id=item.id,
            storage_key=item.file_path,
            storage_backend=item.storage_backend,
            sha256=item.sha256_hash,
        )
    )
    remove(db, MedicationEntry, MedicationEntry.document_id == item.id)
    remove(db, PrescriptionRevision, PrescriptionRevision.document_id == item.id)
    remove(db, DocumentReviewRevision, DocumentReviewRevision.document_id == item.id)
    if job:
        remove(db, DocumentProcessingJob, DocumentProcessingJob.id == job.id)
    remove(db, MedicalDocument, MedicalDocument.id == item.id)
    finish(db, user, item, "document")
    return {"message": "Document removed. File cleanup is queued."}


@router.delete("/clinical/medication-use/{record_id}", status_code=204)
def delete_medication_report(
    record_id: UUID,
    expected_version: int = Query(ge=1),
    expected_review_version: int = Query(ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = owned(db, user, MedicationUse, record_id)
    lock(db, MedicationUse, item, expected_version)
    db.refresh(item)
    if item.review_version != expected_review_version:
        raise HTTPException(409, "Medication review changed. Reload before confirming deletion.")
    remove(db, MedicationReconciliation, MedicationReconciliation.medication_use_id == item.id)
    remove(db, MedicationUseRevision, MedicationUseRevision.medication_use_id == item.id)
    remove(db, MedicationUse, MedicationUse.id == item.id)
    finish(db, user, item, "medication_report")


@router.delete("/clinical/records/{record_id}", status_code=204)
def delete_health_record(
    record_id: UUID,
    expected_version: int = Query(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = owned(db, user, HealthRecord, record_id)
    lock(db, HealthRecord, item, expected_version)
    # Intervention targets are JSON references; retain them unless explicitly reviewed/deleted first.
    if (
        db.query(HealthRevision.id)
        .join(HealthRecord, HealthRecord.id == HealthRevision.record_id)
        .filter(HealthRecord.kind == "intervention", HealthRevision.data["target_id"].as_string() == item.id)
        .first()
    ):
        raise HTTPException(409, "Delete linked intervention records before deleting this care record.")
    revisions = select(HealthRevision.id).where(HealthRevision.record_id == item.id)
    remove(db, NotificationDelivery, NotificationDelivery.record_id == item.id)
    remove(db, FHIRImportLink, FHIRImportLink.revision_id.in_(revisions))
    remove(db, HealthSource, HealthSource.revision_id.in_(revisions))
    remove(db, HealthRevision, HealthRevision.record_id == item.id)
    remove(db, HealthRecord, HealthRecord.id == item.id)
    finish(db, user, item, "health_record")


@router.delete("/clinical/follow-ups/{record_id}", status_code=204)
def delete_follow_up(
    record_id: UUID,
    expected_version: int = Query(ge=1),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    item = owned(db, user, FollowUpTask, record_id)
    parent = db.get(Encounter, item.encounter_id)
    if parent is None or parent.patient_id != item.patient_id:
        raise HTTPException(409, "Follow-up relationship requires review.")
    lock(db, Encounter, parent, parent.version)
    lock(db, FollowUpTask, item, expected_version)
    remove(db, FollowUpRevision, FollowUpRevision.task_id == item.id)
    remove(db, FollowUpTask, FollowUpTask.id == item.id)
    finish(db, user, item, "follow_up")
