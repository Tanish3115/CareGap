"""Deliberately bounded R4 collection adapter, not an ABDM/conformance claim."""

import json
import re
from datetime import date
from fastapi import HTTPException
from app.schemas.health_record import RecordCreate


def export_resource(record, patient_id):
    data = record["data"]
    kind = record["kind"]
    pid = f"urn:uuid:{patient_id}"
    base = dict(
        id=record["id"],
        meta=dict(
            versionId=str(record["version"]),
            tag=[dict(system="https://caregap.local/provenance", code=record["provenance"])],
        ),
        note=[
            dict(
                text=f"Source: CareGap {kind} {record['id']} version {record['version']}. {record['reason']}"
            )
        ],
    )
    if kind == "diagnosis":
        base.update(
            resourceType="Condition",
            subject=dict(reference=pid),
            code=dict(text=data["condition"]),
            recordedDate=str(record["occurred_on"]),
            verificationStatus=dict(
                coding=[
                    dict(
                        system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        code="unconfirmed",
                    )
                ]
            ),
        )
        if data["status"] != "unknown":
            base["clinicalStatus"] = dict(
                coding=[
                    dict(
                        system="http://terminology.hl7.org/CodeSystem/condition-clinical", code=data["status"]
                    )
                ]
            )
    elif kind == "allergy":
        base.update(
            resourceType="AllergyIntolerance",
            patient=dict(reference=pid),
            code=dict(text=data["substance"]),
            recordedDate=str(record["occurred_on"]),
            verificationStatus=dict(
                coding=[
                    dict(
                        system="http://terminology.hl7.org/CodeSystem/allergyintolerance-verification",
                        code="unconfirmed",
                    )
                ]
            ),
        )
        base["clinicalStatus"] = (
            dict(
                coding=[
                    dict(
                        system="http://terminology.hl7.org/CodeSystem/allergyintolerance-clinical",
                        code=data["status"],
                    )
                ]
            )
            if data["status"] != "unknown"
            else dict(
                extension=[
                    dict(
                        url="http://hl7.org/fhir/StructureDefinition/data-absent-reason", valueCode="unknown"
                    )
                ]
            )
        )
        if data.get("reaction"):
            base["reaction"] = [dict(manifestation=[dict(text=data["reaction"])])]
    elif kind == "lab":
        base.update(
            resourceType="Observation",
            subject=dict(reference=pid),
            status="unknown",
            code=dict(text=data["test_name"]),
            effectiveDateTime=str(record["occurred_on"]),
        )
        if data.get("value") is not None:
            base["valueString"] = data["value"]
        if data.get("unit"):
            base["note"].append(dict(text=f"Source unit (not normalized): {data['unit']}"))
        if data.get("reference_range"):
            base["referenceRange"] = [dict(text=data["reference_range"])]
    elif kind in ("medication_order", "dispensing", "confirmed_use"):
        base.update(
            resourceType={
                "medication_order": "MedicationRequest",
                "dispensing": "MedicationDispense",
                "confirmed_use": "MedicationStatement",
            }[kind],
            subject=dict(reference=pid),
            medicationCodeableConcept=dict(text=data["name"]),
            status="unknown",
        )
        if kind == "medication_order":
            base.update(intent="order", reportedBoolean=True, authoredOn=str(record["occurred_on"]))
        elif kind == "confirmed_use":
            base.update(
                status={"taking": "active", "not_taking": "not-taken", "unknown": "unknown"}[data["status"]],
                effectiveDateTime=str(record["occurred_on"]),
            )
        if data.get("dose") or data.get("frequency") or data.get("instructions"):
            base["dosageInstruction" if kind != "confirmed_use" else "dosage"] = [
                dict(
                    text=" | ".join(
                        f"{field}: {data[field]}"
                        for field in ("dose", "frequency", "instructions")
                        if data.get(field)
                    )
                )
            ]
    elif kind in ("referral", "test"):
        base.update(
            resourceType="ServiceRequest",
            subject=dict(reference=pid),
            intent="plan",
            status={
                "pending": "active",
                "completed": "completed",
                "cancelled": "revoked",
                "missed": "unknown",
                "unknown": "unknown",
            }[data["status"]],
            code=dict(text=record["title"]),
            occurrenceDateTime=data["due_on"],
        )
    else:
        # Date-only care plans are Tasks, not fabricated time-booked Appointments.
        base.update(
            resourceType="Task",
            status={
                "pending": "requested",
                "unknown": "draft",
                "missed": "failed",
                "completed": "completed",
                "cancelled": "cancelled",
                "proposed": "draft",
                "assigned": "requested",
                "declined": "rejected",
            }.get(data.get("status"), "draft"),
            intent="plan",
            description=record["title"],
            code=dict(text=kind),
        )
        base["for"] = dict(reference=pid)
        if data.get("due_on"):
            base["restriction"] = dict(period=dict(end=data["due_on"]))
    return base


def parse_bundle(bundle, patient_id, reason):
    if bundle.get("resourceType") != "Bundle" or bundle.get("type") != "collection":
        raise HTTPException(422, "Import accepts an R4 collection Bundle, not executable transactions")
    entries = bundle.get("entry")
    if (
        not isinstance(entries, list)
        or not 1 <= len(entries) <= 50
        or len(json.dumps(bundle, ensure_ascii=False).encode("utf-8")) > 1024 * 1024
    ):
        raise HTTPException(422, "Import limit: 50 entries and one MiB")
    resources = [entry.get("resource") for entry in entries if isinstance(entry, dict)]
    if len(resources) != len(entries) or not all(isinstance(resource, dict) for resource in resources):
        raise HTTPException(422, "Every entry needs a resource object")
    patients = [resource for resource in resources if resource.get("resourceType") == "Patient"]
    if len(patients) != 1 or patients[0].get("id") != patient_id:
        raise HTTPException(
            422,
            "Bundle must contain exactly this internal patient UUID; explicit external identity mapping is not supported",
        )
    result = []
    seen = set()
    for resource in resources:
        resource_type = resource.get("resourceType")
        if resource_type == "Patient":
            continue
        if resource_type not in ("Condition", "AllergyIntolerance", "Observation"):
            raise HTTPException(
                422,
                "Import subset supports only Patient, Condition, AllergyIntolerance and simple Observation resources",
            )
        identity = resource.get("id")
        if (
            not isinstance(identity, str)
            or not re.fullmatch(r"[A-Za-z0-9.-]{1,64}", identity)
            or identity in seen
        ):
            raise HTTPException(422, "Imported clinical resources need unique IDs")
        seen.add(identity)
        subject = resource.get("patient" if resource_type == "AllergyIntolerance" else "subject", {})
        if not isinstance(subject, dict) or not isinstance(resource.get("code"), dict):
            raise HTTPException(422, "Subject and code must be FHIR objects")
        reference = subject.get("reference")
        if reference not in (f"Patient/{patient_id}", f"urn:uuid:{patient_id}"):
            raise HTTPException(
                422, "Every imported resource must refer to this patient; no external references are fetched"
            )
        text = resource.get("code", {}).get("text")
        if not isinstance(text, str) or not text.strip():
            raise HTTPException(
                422, "Import requires explicit source code.text; terminology is never guessed"
            )
        date_text = resource.get("recordedDate") or resource.get("effectiveDateTime")
        try:
            occurred_on = date.fromisoformat(date_text[:10])
        except (TypeError, ValueError):
            raise HTTPException(422, "Import requires an explicit recorded/effective date")
        if resource_type == "Condition":
            data = dict(kind="diagnosis", condition=text, status="unknown")
        elif resource_type == "AllergyIntolerance":
            reactions = resource.get("reaction", [])
            if not isinstance(reactions, list) or any(
                not isinstance(reaction, dict) for reaction in reactions
            ):
                raise HTTPException(422, "Invalid allergy reaction list")
            if reactions and (
                not isinstance(reactions[0].get("manifestation"), list)
                or not reactions[0]["manifestation"]
                or not isinstance(reactions[0]["manifestation"][0], dict)
            ):
                raise HTTPException(422, "Invalid reaction manifestation")
            reaction = reactions[0].get("manifestation", [{}])[0].get("text") if reactions else None
            data = dict(kind="allergy", substance=text, reaction=reaction, status="unknown")
        else:
            if any(key in resource for key in ("component", "valueQuantity", "valueCodeableConcept")):
                raise HTTPException(
                    422,
                    "This import subset accepts simple valueString observations; quantitative/coded mappings need explicit review",
                )
            data = dict(kind="lab", test_name=text, value=resource.get("valueString"))
        try:
            result.append(
                RecordCreate(
                    patient_id=patient_id,
                    title=text,
                    occurred_on=occurred_on,
                    data=data,
                    reason=reason,
                    source_checked=True,
                )
            )
        except ValueError:
            raise HTTPException(
                422, "Imported fields exceed the supported schema or contain an invalid/future date"
            )
    if not result:
        raise HTTPException(422, "Bundle contains no supported clinical resources")
    return result
