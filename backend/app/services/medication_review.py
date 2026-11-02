"""Literal comparison plus an explicitly synthetic provider; never a dosing engine."""

from collections import defaultdict
from app.models.prescription import MedicationEntry, PrescriptionRevision
from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.services.approved_knowledge import evaluate_knowledge
from app.models.health_record import HealthRecord
from app.models.medication_use import MedicationUse, MedicationUseRevision
from app.services.health_records import current_records
from sqlalchemy import and_, func


def review_medications(db, patient_id, include_allergies=True):
    latest = (
        db.query(PrescriptionRevision.document_id, func.max(PrescriptionRevision.version).label("version"))
        .filter_by(state="clinician_confirmed")
        .group_by(PrescriptionRevision.document_id)
        .subquery()
    )
    rows = (
        db.query(MedicationEntry, PrescriptionRevision)
        .join(PrescriptionRevision, PrescriptionRevision.id == MedicationEntry.prescription_revision_id)
        .join(
            latest,
            and_(
                latest.c.document_id == PrescriptionRevision.document_id,
                latest.c.version == PrescriptionRevision.version,
            ),
        )
        .filter(MedicationEntry.patient_id == patient_id)
        .order_by(MedicationEntry.id)
        .limit(501)
        .all()
    )
    evidence = []
    alerts = []
    for entry, revision in rows[:500]:
        doc = db.get(MedicalDocument, entry.document_id)
        source_review = db.get(DocumentReviewRevision, revision.source_review_id)
        evidence.append(
            dict(
                id=entry.id,
                kind="historical_prescription",
                name=entry.name,
                dose=entry.dose,
                frequency=entry.frequency,
                start_on=None,
                end_on=None,
                source_path=f"/medications?patient_id={patient_id}&document_id={doc.id}",
                source_version=revision.version,
                coding=entry.evidence.get("coding")
                if source_review
                and source_review.version == doc.review_version
                and doc.prescription_version == revision.version
                else None,
            )
        )
        if entry.needs_clarification:
            alerts.append(
                dict(
                    type="incomplete_source",
                    evidence_ids=[entry.id],
                    message="Historical prescription fields need clarification. Current use and safe dosing are not established.",
                )
            )
    records = (
        current_records(db, patient_id)
        .filter(
            HealthRecord.kind.in_(
                ("medication_order", "dispensing", "confirmed_use", "allergy")
                if include_allergies
                else ("medication_order", "dispensing", "confirmed_use")
            )
        )
        .limit(501)
        .all()
    )
    allergies = []
    for root, revision in records[:500]:
        data = revision.data
        if root.kind == "allergy":
            if data.get("status") != "inactive":
                allergies.append(dict(substance=data["substance"], id=root.id))
            continue
        if data.get("status") in ("cancelled", "not_taking"):
            continue
        evidence.append(
            dict(
                id=root.id,
                kind=root.kind,
                name=data["name"],
                dose=data.get("dose"),
                frequency=data.get("frequency"),
                start_on=data.get("start_on"),
                end_on=data.get("end_on"),
                source_path=f"/clinical/records/{root.id}",
                source_version=revision.version,
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
        .order_by(MedicationUse.id)
        .limit(501)
        .all()
    )
    for root, revision in uses[:500]:
        evidence.append(
            dict(
                id=root.id,
                kind="patient_reported_use",
                name=revision.name,
                dose=revision.dose,
                frequency=revision.frequency,
                start_on=None,
                end_on=None,
                reported_on=revision.reported_on.isoformat(),
                use_status=revision.use_status,
                source_path=f"/clinical/medication-use/{root.id}/history",
                source_version=revision.version,
            )
        )
    grouped = defaultdict(list)
    for item in evidence:
        grouped[item["name"].strip().casefold()].append(item)
    for group in grouped.values():
        if len(group) < 2:
            continue
        alerts.append(
            dict(
                type="possible_duplicate",
                evidence_ids=[item["id"] for item in group],
                message="Exact reported/source name appears more than once. Entries have not been merged; names alone do not establish equivalent medicines or concurrent use.",
            )
        )
        if len({item["dose"] for item in group if item["dose"]}) > 1:
            alerts.append(
                dict(
                    type="differing_dose_text",
                    evidence_ids=[item["id"] for item in group],
                    message="Recorded dose text differs. Compare sources and dates; no dose recommendation is made.",
                )
            )
        for i, left in enumerate(group[:50]):
            for right in group[i + 1 : 50]:
                if all((left["start_on"], left["end_on"], right["start_on"], right["end_on"])) and max(
                    left["start_on"], right["start_on"]
                ) <= min(left["end_on"], right["end_on"]):
                    alerts.append(
                        dict(
                            type="recorded_period_overlap",
                            evidence_ids=[left["id"], right["id"]],
                            message="Explicit recorded periods overlap. This does not prove simultaneous use.",
                        )
                    )
    # The demo vocabulary has no real medicines or approved terminology mapping.
    synthetic = {
        item["name"].strip().upper(): item
        for item in evidence
        if item["name"].strip().upper() in ("SYNTHETIC-A", "SYNTHETIC-B")
    }
    demonstrations = []
    if set(synthetic) == {"SYNTHETIC-A", "SYNTHETIC-B"}:
        demonstrations.append(
            dict(
                type="synthetic_interaction",
                evidence_ids=[synthetic[name]["id"] for name in sorted(synthetic)],
                provider="synthetic-fixture-v1",
                evidence="CareGap software test fixture A+B; no clinical evidence",
                message="SYNTHETIC DEMONSTRATION: artificial A/B interaction rule; not applicable to real medicines.",
            )
        )
    for allergy in allergies:
        if allergy["substance"].strip().upper() in synthetic:
            demonstrations.append(
                dict(
                    type="synthetic_allergy_match",
                    evidence_ids=[allergy["id"], synthetic[allergy["substance"].strip().upper()]["id"]],
                    provider="synthetic-fixture-v1",
                    evidence="Exact artificial token match only",
                    message="SYNTHETIC DEMONSTRATION: artificial allergy token matches a fixture medicine.",
                )
            )
    knowledge = evaluate_knowledge(evidence)
    return dict(
        mode="literal_comparison",
        approved_knowledge=knowledge,
        evidence=evidence,
        indicators=alerts[:250],
        synthetic_demonstrations=demonstrations,
        clinical_knowledge_provider=knowledge["reference"]
        if knowledge["status"] == "available"
        else knowledge["status"],
        clinical_safety_checked=False,
        allergy_records_included=include_allergies,
        truncated=len(rows) > 500
        or len(records) > 500
        or len(uses) > 500
        or len(alerts) > 250
        or knowledge["findings_truncated"],
        limitations="Real drug interactions, therapeutic equivalence, allergy cross-reactivity and safe doses are not evaluated. A validated provider and approved terminology mappings are required.",
    )
