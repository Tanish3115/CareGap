"""Extractive source-linked overview. No generated clinical conclusions."""

from app.models.clinical import Encounter, EncounterRevision, FollowUpTask, FollowUpRevision
from app.models.medication_use import MedicationUse, MedicationUseRevision, MedicationReconciliation
from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.models.prescription import PrescriptionRevision, MedicationEntry
from app.services.health_records import current_records, record_out
from app.core.clinical_resources import CLINICAL_RESOURCES, KIND_RESOURCE


def summary(db, patient_id, offset=0, limit=50, allowed_resources=None):
    allowed = set(CLINICAL_RESOURCES) if allowed_resources is None else set(allowed_resources)
    from app.models.health_record import HealthRecord, HealthRevision

    rows = current_records(db, patient_id).filter(
        HealthRecord.kind.in_([kind for kind, group in KIND_RESOURCE.items() if group in allowed])
    )
    rows = (
        rows.order_by(HealthRevision.occurred_on.desc(), HealthRecord.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    facts = [
        dict(
            category=root.kind,
            provenance=rev.provenance,
            source_id=root.id,
            source_version=rev.version,
            source_path=f"/clinical/records/{root.id}",
            title=rev.title,
            date=rev.occurred_on.isoformat(),
            details=rev.data,
            documents=record_out(db, root, rev)["sources"],
        )
        for root, rev in rows[:limit]
    ]
    # Independent bounded pages prevent a large category from hiding others.
    encounters = (
        db.query(Encounter, EncounterRevision)
        .join(
            EncounterRevision,
            (EncounterRevision.encounter_id == Encounter.id)
            & (EncounterRevision.version == Encounter.version),
        )
        .filter(Encounter.patient_id == patient_id)
        .order_by(EncounterRevision.occurred_on.desc(), Encounter.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
        if "consultations" in allowed
        else []
    )
    for root, rev in encounters[:limit]:
        facts.append(
            dict(
                category="consultation",
                provenance=rev.provenance,
                source_id=root.id,
                source_version=rev.version,
                source_path=f"/clinical/encounters/{root.id}",
                title=rev.title,
                date=rev.occurred_on.isoformat(),
                details=dict(notes=rev.notes),
                documents=[
                    dict(id=link.document_id, title=link.document.title, file_name=link.document.file_name)
                    for link in rev.sources
                ],
            )
        )
    uses = (
        db.query(MedicationUse, MedicationUseRevision)
        .join(
            MedicationUseRevision,
            (MedicationUseRevision.medication_use_id == MedicationUse.id)
            & (MedicationUseRevision.version == MedicationUse.version),
        )
        .filter(MedicationUse.patient_id == patient_id)
        .order_by(MedicationUse.updated_at.desc(), MedicationUse.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
        if "medications" in allowed
        else []
    )
    for root, rev in uses[:limit]:
        review = (
            db.query(MedicationReconciliation)
            .filter_by(medication_use_id=root.id, version=root.review_version)
            .first()
        )
        facts.append(
            dict(
                category="reported_medication_use",
                provenance="patient_reported",
                source_id=root.id,
                source_version=rev.version,
                source_path=f"/clinical/medication-use/{root.id}/history",
                title=rev.name,
                date=rev.reported_on.isoformat(),
                details=dict(
                    use_status=rev.use_status,
                    dose=rev.dose,
                    frequency=rev.frequency,
                    notes=rev.notes,
                    clinician_assessment=review.assessment if review else None,
                    assessment_applies_to_this_report=bool(review and review.report_revision_id == rev.id),
                ),
                documents=[],
            )
        )
    tasks = (
        db.query(FollowUpTask, FollowUpRevision)
        .join(
            FollowUpRevision,
            (FollowUpRevision.task_id == FollowUpTask.id)
            & (FollowUpRevision.version == FollowUpTask.version),
        )
        .filter(FollowUpTask.patient_id == patient_id)
        .order_by(FollowUpRevision.due_on, FollowUpTask.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
        if "follow_ups" in allowed
        else []
    )
    for root, rev in tasks[:limit]:
        facts.append(
            dict(
                category="follow_up",
                provenance=rev.provenance,
                source_id=root.id,
                source_version=rev.version,
                source_path=f"/clinical/follow-ups/{root.id}/history",
                title=rev.title,
                date=rev.due_on.isoformat(),
                details=dict(status=rev.status, outcome=rev.outcome),
                documents=[],
            )
        )
    # Query latest confirmation per document, preserving the historical-use distinction.
    from sqlalchemy import func, and_

    latest = (
        db.query(PrescriptionRevision.document_id, func.max(PrescriptionRevision.version).label("version"))
        .filter_by(state="clinician_confirmed")
        .group_by(PrescriptionRevision.document_id)
        .subquery()
    )
    prescriptions = (
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
        .filter(MedicationEntry.patient_id == patient_id)
        .order_by(MedicationEntry.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
        if "medications" in allowed
        else []
    )
    for entry, revision, doc, source in prescriptions[:limit]:
        facts.append(
            dict(
                category="historical_prescription",
                provenance="clinician_reviewed_transcription",
                source_id=doc.id,
                source_version=revision.version,
                source_path=f"/medications?patient_id={patient_id}&document_id={doc.id}",
                title=entry.name,
                date=entry.created_at.date().isoformat(),
                details=dict(
                    strength=entry.strength,
                    dose=entry.dose,
                    frequency=entry.frequency,
                    route=entry.route,
                    duration=entry.duration,
                    instructions=entry.instructions,
                    source_stale=source.version != doc.review_version,
                    newer_draft=doc.prescription_version > revision.version,
                ),
                documents=[dict(id=doc.id, title=doc.title, file_name=doc.file_name)],
            )
        )
    return dict(
        mode="source_extracts",
        interpretations=[],
        facts=sorted(facts, key=lambda fact: (fact["date"], fact["source_id"]), reverse=True),
        offset=offset,
        limit_per_category=limit,
        clinical_resources=sorted(allowed),
        has_more=any(len(page) > limit for page in (rows, encounters, uses, tasks, prescriptions)),
        missing_information="No entry means unrecorded or outside this page, never confirmed absence. Source labels describe authorship, not independent clinical validation.",
    )
