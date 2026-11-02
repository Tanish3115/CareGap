from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import inspect
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.models.document import MedicalDocument
from app.models.clinical import Encounter, EncounterRevision, EncounterSource, FollowUpTask, FollowUpRevision
from app.models.health_record import HealthRecord, HealthRevision, HealthSource
from app.models.medication_use import MedicationUse, MedicationUseRevision, MedicationReconciliation
from app.models.prescription import PrescriptionRevision, MedicationEntry
from app.models.document_review import DocumentReviewRevision
from app.models.operations import PrivacyRequest
from app.models.coordination import NotificationDelivery
from app.models.consent import ConsentGrant
from app.models.interoperability import FHIRImport, FHIRImportLink
from app.services.audit_service import audit_service

router = APIRouter(tags=["Patient-owned paged data export"])


def columns(row, exclude=()):
    return {
        attribute.key: getattr(row, attribute.key)
        for attribute in inspect(type(row)).column_attrs
        if attribute.key not in exclude
    }


@router.get("/privacy/export")
def export_page(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.role != "patient":
        raise HTTPException(403, "Only the patient owner can export personal records")
    patient = user.patient_profile
    target = patient.id
    queries = {
        "consultations": (db.query(Encounter).filter_by(patient_id=target), Encounter, ()),
        "follow_ups": (db.query(FollowUpTask).filter_by(patient_id=target), FollowUpTask, ()),
        "structured_record_identities": (
            db.query(HealthRecord).filter_by(patient_id=target),
            HealthRecord,
            (),
        ),
        "medication_use_identities": (
            db.query(MedicationUse).filter_by(patient_id=target),
            MedicationUse,
            (),
        ),
        "consultation_source_links": (
            db.query(EncounterSource)
            .join(EncounterRevision, EncounterRevision.id == EncounterSource.revision_id)
            .join(Encounter, Encounter.id == EncounterRevision.encounter_id)
            .filter(Encounter.patient_id == target),
            EncounterSource,
            (),
        ),
        "structured_source_links": (
            db.query(HealthSource)
            .join(HealthRevision, HealthRevision.id == HealthSource.revision_id)
            .join(HealthRecord, HealthRecord.id == HealthRevision.record_id)
            .filter(HealthRecord.patient_id == target),
            HealthSource,
            (),
        ),
        "fhir_source_links": (
            db.query(FHIRImportLink)
            .join(FHIRImport, FHIRImport.id == FHIRImportLink.import_id)
            .filter(FHIRImport.patient_id == target),
            FHIRImportLink,
            (),
        ),
        "documents": (
            db.query(MedicalDocument).filter_by(patient_id=target),
            MedicalDocument,
            ("file_path",),
        ),
        "consultation_revisions": (
            db.query(EncounterRevision)
            .join(Encounter, Encounter.id == EncounterRevision.encounter_id)
            .filter(Encounter.patient_id == target),
            EncounterRevision,
            (),
        ),
        "follow_up_revisions": (
            db.query(FollowUpRevision)
            .join(FollowUpTask, FollowUpTask.id == FollowUpRevision.task_id)
            .filter(FollowUpTask.patient_id == target),
            FollowUpRevision,
            (),
        ),
        "structured_revisions": (
            db.query(HealthRevision)
            .join(HealthRecord, HealthRecord.id == HealthRevision.record_id)
            .filter(HealthRecord.patient_id == target),
            HealthRevision,
            (),
        ),
        "medication_use_revisions": (
            db.query(MedicationUseRevision)
            .join(MedicationUse, MedicationUse.id == MedicationUseRevision.medication_use_id)
            .filter(MedicationUse.patient_id == target),
            MedicationUseRevision,
            (),
        ),
        "reconciliations": (
            db.query(MedicationReconciliation)
            .join(MedicationUse, MedicationUse.id == MedicationReconciliation.medication_use_id)
            .filter(MedicationUse.patient_id == target),
            MedicationReconciliation,
            (),
        ),
        "prescription_revisions": (
            db.query(PrescriptionRevision)
            .join(MedicalDocument, MedicalDocument.id == PrescriptionRevision.document_id)
            .filter(MedicalDocument.patient_id == target),
            PrescriptionRevision,
            (),
        ),
        "historical_medication_entries": (
            db.query(MedicationEntry).filter_by(patient_id=target),
            MedicationEntry,
            (),
        ),
        "source_reviews": (
            db.query(DocumentReviewRevision)
            .join(MedicalDocument, MedicalDocument.id == DocumentReviewRevision.document_id)
            .filter(MedicalDocument.patient_id == target),
            DocumentReviewRevision,
            (),
        ),
        "consent_grants": (db.query(ConsentGrant).filter_by(patient_id=target), ConsentGrant, ()),
        "local_notification_history": (
            db.query(NotificationDelivery).filter_by(patient_id=target),
            NotificationDelivery,
            (),
        ),
        "privacy_requests": (db.query(PrivacyRequest).filter_by(user_id=user.id), PrivacyRequest, ()),
        "fhir_source_metadata": (
            db.query(FHIRImport).filter_by(patient_id=target),
            FHIRImport,
            ("original",),
        ),
    }
    pages = {}
    has_more = False
    for name, (query, model, exclude) in queries.items():
        rows = query.order_by(*inspect(model).primary_key).offset(offset).limit(limit + 1).all()
        pages[name] = [columns(row, exclude) for row in rows[:limit]]
        has_more = has_more or len(rows) > limit
    audit_service.log_event(
        db, "EXPORT_PERSONAL_RECORDS", "privacy_export", actor_id=user.id, patient_id=target
    )
    return dict(
        account={key: getattr(user, key) for key in ("id", "full_name", "email", "phone", "role")},
        profile=columns(patient),
        pages=pages,
        offset=offset,
        limit_per_category=limit,
        has_more=has_more,
        scope="Paged source/record extract. Originals use authenticated document downloads and FHIR import-source endpoints. Concurrent changes may require a new export. Passwords, session tokens and infrastructure secrets are excluded.",
    )
