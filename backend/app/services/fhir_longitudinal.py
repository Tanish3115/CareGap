"""R4 collection mappings for current authorized accounts, not a FHIR server."""

import base64
from datetime import timezone
from fastapi import HTTPException
from app.models.user import User
from app.models.clinical import Encounter, EncounterRevision, FollowUpTask, FollowUpRevision
from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.models.health_record import HealthRecord, HealthRevision
from app.models.medication_use import MedicationUse, MedicationUseRevision
from app.models.prescription import MedicationEntry, PrescriptionRevision
from app.services.health_records import record_out
from app.services.fhir_adapter import export_resource

EXT = "https://caregap.local/fhir/StructureDefinition/"


def instant(value):
    return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")


def literal_medication_fields(data):
    return " | ".join(
        f"{key}: {data[key]}"
        for key in ("strength", "dose", "route", "frequency", "duration", "instructions")
        if data.get(key)
    )


def export_entry(db, entry, patient_id):
    kind, identifier = entry["kind"], entry["id"]
    patient = dict(reference=f"urn:uuid:{patient_id}")
    extra, sources = [], []
    if kind == "document":
        doc = db.get(MedicalDocument, identifier)
        if not doc:
            raise HTTPException(409, "Export source changed. Reload the page.")
        actor, recorded = doc.uploader_id, doc.created_at
        resource = dict(
            resourceType="DocumentReference",
            id=identifier,
            status="current",
            subject=patient,
            description=doc.title,
            date=instant(doc.created_at),
            type=dict(text=doc.document_type),
            content=[
                dict(
                    attachment=dict(
                        contentType=doc.mime_type,
                        title=doc.file_name,
                        size=doc.file_size,
                        url=f"/api/v1/documents/{identifier}/download",
                        extension=[dict(url=EXT + "sha256", valueString=doc.sha256_hash)],
                    )
                )
            ],
        )
        if doc.clinical_date:
            resource["context"] = dict(period=dict(start=doc.clinical_date.isoformat()))
    elif kind == "encounter":
        root = db.get(Encounter, identifier)
        revision = (
            db.query(EncounterRevision).filter_by(encounter_id=identifier, version=root.version).one()
            if root
            else None
        )
        if not revision:
            raise HTTPException(409, "Export source changed. Reload the page.")
        actor, recorded = revision.recorded_by, revision.created_at
        resource = dict(
            resourceType="Encounter",
            id=identifier,
            status="unknown",
            subject=patient,
            period=dict(start=revision.occurred_on.isoformat()),
            extension=[dict(url=EXT + "record-title", valueString=revision.title)],
        )
        # The source doesn't establish ambulatory/inpatient classification.
        resource["class"] = dict(
            extension=[
                dict(url="http://hl7.org/fhir/StructureDefinition/data-absent-reason", valueCode="unknown")
            ]
        )
        extra.append(
            dict(
                resourceType="DocumentReference",
                id=identifier + "-note",
                status="current",
                subject=patient,
                description=revision.title,
                context=dict(encounter=[dict(reference=f"urn:uuid:{identifier}")]),
                content=[
                    dict(
                        attachment=dict(
                            contentType="text/plain",
                            data=base64.b64encode(revision.notes.encode("utf-8")).decode("ascii"),
                        )
                    )
                ],
            )
        )
        sources = [link.document_id for link in revision.sources]
    elif kind == "follow_up":
        root = db.get(FollowUpTask, identifier)
        revision = (
            db.query(FollowUpRevision).filter_by(task_id=identifier, version=root.version).one()
            if root
            else None
        )
        if not revision:
            raise HTTPException(409, "Export source changed. Reload the page.")
        actor, recorded = revision.recorded_by, revision.created_at
        resource = dict(
            resourceType="Task",
            id=identifier,
            status={"pending": "requested", "completed": "completed", "cancelled": "cancelled"}[
                revision.status
            ],
            intent="plan",
            description=revision.title,
            restriction=dict(period=dict(end=revision.due_on.isoformat())),
        )
        resource["for"] = patient
        if revision.outcome:
            resource["output"] = [dict(type=dict(text="Reported outcome"), valueString=revision.outcome)]
    elif kind == "reported_medication_use":
        root = db.get(MedicationUse, identifier)
        revision = (
            db.query(MedicationUseRevision)
            .filter_by(medication_use_id=identifier, version=root.version)
            .one()
            if root
            else None
        )
        if not revision:
            raise HTTPException(409, "Export source changed. Reload the page.")
        actor, recorded = revision.recorded_by, revision.created_at
        resource = dict(
            resourceType="MedicationStatement",
            id=identifier,
            subject=patient,
            status={"taking": "active", "not_taking": "not-taken", "unknown": "unknown"}[revision.use_status],
            medicationCodeableConcept=dict(text=revision.name),
            effectiveDateTime=revision.reported_on.isoformat(),
            informationSource=patient,
            note=[dict(text=revision.notes or "Patient-reported medication account")],
        )
        instruction = literal_medication_fields(dict(dose=revision.dose, frequency=revision.frequency))
        if instruction:
            resource["dosage"] = [dict(text=instruction)]
        if revision.source_entry_id:
            source = db.get(MedicationEntry, revision.source_entry_id)
            if source:
                sources = [source.document_id]
    elif kind == "historical_prescription":
        item = db.get(MedicationEntry, identifier)
        revision = db.get(PrescriptionRevision, item.prescription_revision_id) if item else None
        doc = db.get(MedicalDocument, item.document_id) if item else None
        if not revision or not doc:
            raise HTTPException(409, "Export source changed. Reload the page.")
        actor, recorded = revision.author_id, revision.created_at
        resource = dict(
            resourceType="MedicationRequest",
            id=identifier,
            subject=patient,
            status="unknown",
            intent="order",
            reportedBoolean=True,
            medicationCodeableConcept=dict(text=item.name),
            note=[
                dict(
                    text="Historical prescription transcription; not a new order, dispensing record or current-use statement"
                )
            ],
        )
        coding = item.evidence.get("coding")
        if coding:
            from app.schemas.terminology import TerminologyCoding

            coding = TerminologyCoding.model_validate(coding)
            if coding.checked and not coding.uncertain:
                resource["medicationCodeableConcept"]["coding"] = [
                    dict(
                        system=coding.system, version=coding.release, code=coding.code, display=coding.display
                    )
                ]
                resource["note"].append(
                    dict(text="Reviewed terminology evidence: " + coding.evidence_reference)
                )
                if coding.mode == "synthetic":
                    resource["note"].append(
                        dict(text="Synthetic terminology fixture, not a real medication mapping")
                    )
        instruction = literal_medication_fields(
            {
                key: getattr(item, key)
                for key in ("strength", "dose", "route", "frequency", "duration", "instructions")
            }
        )
        if instruction:
            resource["dosageInstruction"] = [dict(text=instruction)]
        if doc.clinical_date:
            resource["authoredOn"] = doc.clinical_date.isoformat()
        sources = [doc.id]
    elif kind == "transcription_review":
        revision = db.get(DocumentReviewRevision, identifier)
        if not revision:
            raise HTTPException(409, "Export source changed. Reload the page.")
        actor, recorded = revision.reviewer_id, revision.created_at
        resource = dict(
            resourceType="DocumentReference",
            id=identifier,
            status="current",
            subject=patient,
            description="Reviewed source transcription; authorship does not establish clinical validation",
            content=[
                dict(
                    attachment=dict(
                        contentType="text/plain",
                        data=base64.b64encode(revision.reviewed_text.encode("utf-8")).decode("ascii"),
                    )
                )
            ],
        )
        sources = [revision.document_id]
    else:
        root = db.get(HealthRecord, identifier)
        revision = (
            db.query(HealthRevision).filter_by(record_id=identifier, version=root.version).one()
            if root
            else None
        )
        if not revision:
            raise HTTPException(409, "Export source changed. Reload the page.")
        actor, recorded = revision.recorded_by, revision.created_at
        resource = export_resource(record_out(db, root, revision), patient_id)
        sources = [link.document_id for link in revision.sources]
    resource.setdefault("meta", {})["tag"] = [
        dict(system="https://caregap.local/provenance", code=entry["provenance"])
    ]
    if entry["version"]:
        resource["meta"]["versionId"] = str(entry["version"])
    user = db.get(User, actor)
    if user.role == "doctor":
        who = dict(reference=f"urn:uuid:{user.id}")
        extra.append(dict(resourceType="Practitioner", id=user.id, name=[dict(text=user.full_name)]))
    else:
        who = patient
    provenance = dict(
        resourceType="Provenance",
        id=identifier + "-provenance",
        recorded=instant(recorded),
        target=[dict(reference=f"urn:uuid:{identifier}")],
        agent=[dict(who=who)],
        entity=[
            dict(
                role="source",
                what=dict(identifier=dict(system="https://caregap.local/document-id", value=source)),
            )
            for source in sources
        ],
    )
    if not sources:
        provenance.pop("entity")
    return [resource, *extra, provenance]
