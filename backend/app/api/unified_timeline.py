"""Current-version longitudinal timeline; consent filters precede search/pagination."""

from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import Date, Integer, String, and_, case, func, literal, select, union_all
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.api.clinical import authorize_patient
from app.core.clinical_resources import KIND_RESOURCE
from app.models.clinical import Encounter, EncounterRevision, FollowUpTask, FollowUpRevision
from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.models.health_record import HealthRecord, HealthRevision
from app.models.medication_use import MedicationUse, MedicationUseRevision
from app.models.prescription import MedicationEntry, PrescriptionRevision
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.authorization import allowed_clinical_resources, document_filter

router = APIRouter(prefix="/clinical", tags=["Unified authorized timeline"])
TimelineKind = Literal[
    "document",
    "encounter",
    "follow_up",
    "reported_medication_use",
    "historical_prescription",
    "transcription_review",
    "diagnosis",
    "allergy",
    "lab",
    "appointment",
    "referral",
    "test",
    "medication_order",
    "dispensing",
    "confirmed_use",
    "intervention",
]
GROUPS = {
    **KIND_RESOURCE,
    "encounter": "consultations",
    "follow_up": "follow_ups",
    "reported_medication_use": "medications",
    "historical_prescription": "medications",
    "transcription_review": "source_reviews",
}


class TimelineEntry(BaseModel):
    id: str
    kind: TimelineKind
    event_date: date
    date_basis: str
    title: str
    provenance: str
    version: int | None
    source_path: str
    history_path: str | None
    document_id: str | None
    file_name: str | None


def row_columns(
    identifier,
    kind,
    event_date,
    date_basis,
    title,
    provenance,
    version,
    source_path,
    history_path=None,
    doc=None,
    filename=None,
):
    def expression(value, sqltype=None):
        return value if hasattr(value, "label") else literal(value, type_=sqltype)

    return [
        expression(value, sqltype).label(name)
        for name, value, sqltype in (
            ("id", identifier, String),
            ("kind", kind, String),
            ("event_date", event_date, Date),
            ("date_basis", date_basis, String),
            ("title", title, String),
            ("provenance", provenance, String),
            ("version", version, Integer),
            ("source_path", source_path, String),
            ("history_path", history_path, String),
            ("document_id", doc, String),
            ("file_name", filename, String),
        )
    ]


@router.get("/unified-timeline", response_model=list[TimelineEntry])
def timeline(
    patient_id: UUID,
    request: Request,
    kind: TimelineKind | None = None,
    search: str = Query("", max_length=100, pattern=r"^[^\x00]*$"),
    date_from: date | None = None,
    date_to: date | None = None,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    authorize_patient(db, user, target, request, any_resource=True)
    allowed = allowed_clinical_resources(db, user, target)
    if kind and kind != "document" and GROUPS[kind] not in allowed:
        raise HTTPException(403, "This clinical timeline group has not been shared")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, "Timeline start date must not follow the end date")
    parts = [
        select(
            *row_columns(
                MedicalDocument.id,
                "document",
                func.coalesce(
                    MedicalDocument.clinical_date, func.date(MedicalDocument.created_at, type_=Date)
                ),
                case((MedicalDocument.clinical_date.is_not(None), "clinical_date"), else_="upload_date"),
                MedicalDocument.title,
                "source_unverified",
                None,
                literal("/documents/") + MedicalDocument.id,
                doc=MedicalDocument.id,
                filename=MedicalDocument.file_name,
            )
        ).where(MedicalDocument.patient_id == target, document_filter(db, user, target))
    ]
    if "consultations" in allowed:
        parts.append(
            select(
                *row_columns(
                    Encounter.id,
                    "encounter",
                    EncounterRevision.occurred_on,
                    "consultation_date",
                    EncounterRevision.title,
                    EncounterRevision.provenance,
                    Encounter.version,
                    literal("/clinical/encounters/") + Encounter.id,
                    literal("/clinical/encounters/") + Encounter.id + literal("/history"),
                )
            )
            .join(
                EncounterRevision,
                and_(
                    EncounterRevision.encounter_id == Encounter.id,
                    EncounterRevision.version == Encounter.version,
                ),
            )
            .where(Encounter.patient_id == target)
        )
    if "follow_ups" in allowed:
        parts.append(
            select(
                *row_columns(
                    FollowUpTask.id,
                    "follow_up",
                    FollowUpRevision.due_on,
                    "due_date",
                    FollowUpRevision.title,
                    FollowUpRevision.provenance,
                    FollowUpTask.version,
                    literal("/clinical/follow-ups/") + FollowUpTask.id,
                    literal("/clinical/follow-ups/") + FollowUpTask.id + literal("/history"),
                )
            )
            .join(
                FollowUpRevision,
                and_(
                    FollowUpRevision.task_id == FollowUpTask.id,
                    FollowUpRevision.version == FollowUpTask.version,
                ),
            )
            .where(FollowUpTask.patient_id == target)
        )
    kinds = [key for key, group in KIND_RESOURCE.items() if group in allowed]
    if kinds:
        care = HealthRecord.kind.in_(("appointment", "referral", "test"))
        parts.append(
            select(
                *row_columns(
                    HealthRecord.id,
                    HealthRecord.kind,
                    case(
                        (care, func.date(HealthRevision.data["due_on"].as_string(), type_=Date)),
                        else_=HealthRevision.occurred_on,
                    ),
                    case((care, "due_date"), else_="record_date"),
                    HealthRevision.title,
                    HealthRevision.provenance,
                    HealthRecord.version,
                    literal("/clinical/records/") + HealthRecord.id,
                    literal("/clinical/records/") + HealthRecord.id + literal("/history"),
                )
            )
            .join(
                HealthRevision,
                and_(
                    HealthRevision.record_id == HealthRecord.id,
                    HealthRevision.version == HealthRecord.version,
                ),
            )
            .where(HealthRecord.patient_id == target, HealthRecord.kind.in_(kinds))
        )
    if "medications" in allowed:
        parts.append(
            select(
                *row_columns(
                    MedicationUse.id,
                    "reported_medication_use",
                    MedicationUseRevision.reported_on,
                    "reported_date",
                    MedicationUseRevision.name,
                    "patient_reported",
                    MedicationUse.version,
                    literal("/clinical/medication-use/") + MedicationUse.id + literal("/history?limit=1"),
                    literal("/clinical/medication-use/") + MedicationUse.id + literal("/history"),
                )
            )
            .join(
                MedicationUseRevision,
                and_(
                    MedicationUseRevision.medication_use_id == MedicationUse.id,
                    MedicationUseRevision.version == MedicationUse.version,
                ),
            )
            .where(MedicationUse.patient_id == target)
        )
        latest = (
            select(PrescriptionRevision.document_id, func.max(PrescriptionRevision.version).label("version"))
            .where(PrescriptionRevision.state == "clinician_confirmed")
            .group_by(PrescriptionRevision.document_id)
            .subquery()
        )
        history = (
            (literal("/documents/") + MedicalDocument.id + literal("/prescription/history"))
            if "source_reviews" in allowed
            else None
        )
        parts.append(
            select(
                *row_columns(
                    MedicationEntry.id,
                    "historical_prescription",
                    func.coalesce(
                        MedicalDocument.clinical_date, func.date(MedicationEntry.created_at, type_=Date)
                    ),
                    case((MedicalDocument.clinical_date.is_not(None), "clinical_date"), else_="record_date"),
                    MedicationEntry.name,
                    "clinician_reviewed_transcription",
                    PrescriptionRevision.version,
                    literal(f"/medications?patient_id={target}&document_id=") + MedicalDocument.id,
                    history,
                    MedicalDocument.id,
                    MedicalDocument.file_name,
                )
            )
            .join(PrescriptionRevision, PrescriptionRevision.id == MedicationEntry.prescription_revision_id)
            .join(
                latest,
                and_(
                    latest.c.document_id == PrescriptionRevision.document_id,
                    latest.c.version == PrescriptionRevision.version,
                ),
            )
            .join(MedicalDocument, MedicalDocument.id == MedicationEntry.document_id)
            .where(
                MedicationEntry.patient_id == target,
                MedicalDocument.patient_id == target,
                document_filter(db, user, target),
            )
        )
    if "source_reviews" in allowed:
        parts.append(
            select(
                *row_columns(
                    DocumentReviewRevision.id,
                    "transcription_review",
                    func.date(DocumentReviewRevision.created_at, type_=Date),
                    "record_date",
                    MedicalDocument.title + literal(" — transcription review"),
                    DocumentReviewRevision.reviewer_kind,
                    DocumentReviewRevision.version,
                    literal("/documents/") + MedicalDocument.id + literal("/review"),
                    literal("/documents/") + MedicalDocument.id + literal("/review/history"),
                    MedicalDocument.id,
                    MedicalDocument.file_name,
                )
            )
            .join(
                MedicalDocument,
                and_(
                    MedicalDocument.id == DocumentReviewRevision.document_id,
                    MedicalDocument.review_version == DocumentReviewRevision.version,
                ),
            )
            .where(MedicalDocument.patient_id == target, document_filter(db, user, target))
        )
    combined = union_all(*parts).subquery()
    query = select(combined)
    if kind:
        query = query.where(combined.c.kind == kind)
    if search.strip():
        query = query.where(combined.c.title.icontains(search.strip(), autoescape=True))
    if date_from:
        query = query.where(combined.c.event_date >= date_from)
    if date_to:
        query = query.where(combined.c.event_date <= date_to)
    result = (
        db.execute(
            query.order_by(combined.c.event_date.desc(), combined.c.kind, combined.c.id)
            .offset(offset)
            .limit(limit)
        )
        .mappings()
        .all()
    )
    audit_service.log_event(
        db, "VIEW_UNIFIED_TIMELINE", "clinical_timeline", actor_id=user.id, patient_id=target
    )
    return result
