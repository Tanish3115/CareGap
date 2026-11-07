import hashlib
import json
from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, field_validator
from app.core.input_text import safe_text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_current_patient, get_db
from app.api.clinical import authorize_patient
from app.models.user import User
from app.models.health_record import HealthRecord, HealthRevision
from app.models.interoperability import FHIRImport, FHIRImportLink
from app.schemas.health_record import Reason
from app.services.health_records import current_records, record_out
from app.services.fhir_adapter import export_resource, parse_bundle
from app.services.audit_service import audit_service
from app.services.authorization import allowed_clinical_resources, require_clinical_access
from app.core.clinical_resources import KIND_RESOURCE

router = APIRouter(prefix="/clinical/fhir", tags=["Bounded FHIR R4 adapters"])


@router.get("/longitudinal")
def longitudinal_export(
    patient_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from app.api.unified_timeline import timeline
    from app.services.fhir_longitudinal import export_entry

    target = str(patient_id)
    rows = timeline(
        patient_id=patient_id,
        request=request,
        kind=None,
        search="",
        date_from=None,
        date_to=None,
        limit=limit + 1,
        offset=offset,
        user=user,
        db=db,
    )
    resources = [dict(resourceType="Patient", id=target)]
    for entry in rows[:limit]:
        resources.extend(export_entry(db, entry, target))
    unique = {(resource["resourceType"], resource["id"]): resource for resource in resources}
    result = dict(
        resourceType="Bundle",
        type="collection",
        entry=[dict(fullUrl=f"urn:uuid:{resource['id']}", resource=resource) for resource in unique.values()],
        meta=dict(tag=[dict(system="https://caregap.local/adapter", code="longitudinal-r4-local-mappings")]),
    )
    if len(rows) > limit:
        result["link"] = [
            dict(
                relation="next",
                url=f"/api/v1/clinical/fhir/longitudinal?patient_id={target}&limit={limit}&offset={offset + limit}",
            )
        ]
    audit_service.log_event(db, "EXPORT_LONGITUDINAL_FHIR", "fhir", actor_id=user.id, patient_id=target)
    return result


@router.get("/consents")
def consent_export(
    ctx=Depends(get_current_patient),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
):
    from app.models.consent import ConsentGrant
    from app.models.doctor import Doctor
    from app.core.clinical_resources import valid_resources
    from app.services.fhir_longitudinal import EXT, instant
    from app.services.authorization import active_grants

    user, patient = ctx
    grants = (
        db.query(ConsentGrant)
        .filter_by(patient_id=patient.id)
        .order_by(ConsentGrant.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    resources = [dict(resourceType="Patient", id=patient.id)]
    for grant in grants[:limit]:
        doctor = db.get(Doctor, grant.doctor_id)
        active = (
            not grant.is_revoked
            and doctor.user.is_active
            and doctor.verification_status == "verified"
            and grant in active_grants(db, doctor.id, patient.id)
        )
        resources.append(
            dict(resourceType="Practitioner", id=doctor.user_id, name=[dict(text=doctor.user.full_name)])
        )
        resources.append(
            dict(
                resourceType="Consent",
                id=grant.id,
                status="active" if active else "inactive",
                scope=dict(
                    coding=[
                        dict(
                            system="http://terminology.hl7.org/CodeSystem/consentscope",
                            code="patient-privacy",
                        )
                    ]
                ),
                category=[dict(text="Patient-authorized record sharing")],
                patient=dict(reference=f"urn:uuid:{patient.id}"),
                dateTime=instant(grant.created_at),
                policyRule=dict(text="CareGap local authorization; this export does not grant access"),
                provision=dict(
                    type="permit",
                    period=dict(start=instant(grant.valid_from), end=instant(grant.valid_until)),
                    actor=[
                        dict(
                            role=dict(text="Authorized recipient"),
                            reference=dict(reference=f"urn:uuid:{doctor.user_id}"),
                        )
                    ],
                ),
                extension=[
                    dict(
                        url=EXT + "local-sharing-scope",
                        valueString=json.dumps(
                            dict(
                                document_category=grant.scope,
                                selected_document_ids=grant.document_ids,
                                allow_upload=grant.allow_upload,
                                clinical_resources=sorted(valid_resources(grant.clinical_resources))
                                if grant.include_clinical_records
                                else [],
                                allow_clinical_write=grant.allow_clinical_write,
                                purpose=grant.purpose,
                            )
                        ),
                    )
                ],
            )
        )
    unique = {(resource["resourceType"], resource["id"]): resource for resource in resources}
    result = dict(
        resourceType="Bundle",
        type="collection",
        entry=[dict(fullUrl=f"urn:uuid:{resource['id']}", resource=resource) for resource in unique.values()],
    )
    if len(grants) > limit:
        result["link"] = [
            dict(relation="next", url=f"/api/v1/clinical/fhir/consents?limit={limit}&offset={offset + limit}")
        ]
    audit_service.log_event(
        db, "EXPORT_PATIENT_CONSENT_FHIR", "fhir", actor_id=user.id, patient_id=patient.id
    )
    return result


class ImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    _safe_text = field_validator("*", mode="after")(safe_text)
    patient_id: UUID
    bundle: dict
    reason: Reason
    source_checked: Literal[True]


@router.get("/export")
def export(
    patient_id: UUID,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    authorize_patient(db, user, target, request, any_resource=True)
    allowed = allowed_clinical_resources(db, user, target)
    rows = (
        current_records(db, target)
        .filter(HealthRecord.kind.in_([kind for kind, group in KIND_RESOURCE.items() if group in allowed]))
        .order_by(HealthRecord.id)
        .offset(offset)
        .limit(limit + 1)
        .all()
    )
    entries = [dict(fullUrl=f"urn:uuid:{target}", resource=dict(resourceType="Patient", id=target))]
    for root, revision in rows[:limit]:
        entries.append(
            dict(
                fullUrl=f"urn:uuid:{root.id}",
                resource=export_resource(record_out(db, root, revision), target),
            )
        )
    result = dict(
        resourceType="Bundle",
        type="collection",
        entry=entries,
        meta=dict(
            tag=[dict(system="https://caregap.local/adapter", code="r4-subset-not-conformance-certified")]
        ),
    )
    if len(rows) > limit:
        result["link"] = [
            dict(
                relation="next",
                url=f"/api/v1/clinical/fhir/export?patient_id={target}&limit={limit}&offset={offset + limit}",
            )
        ]
    audit_service.log_event(db, "EXPORT_FHIR_SUBSET", "fhir", actor_id=user.id, patient_id=target)
    return result


@router.post("/preview")
def preview(
    payload: ImportPayload,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(payload.patient_id)
    authorize_patient(db, user, target, request, write=True, any_resource=True)
    rows = parse_bundle(payload.bundle, target, payload.reason)
    require_clinical_access(
        db, user, target, request, write=True, resource={KIND_RESOURCE[row.data.kind] for row in rows}
    )
    return dict(
        mode="unverified_source_import",
        records=[row.model_dump(mode="json") for row in rows],
        warning="Review every assertion. Imported statuses do not establish independent clinical verification.",
    )


@router.post("/import", status_code=201)
def import_bundle(
    payload: ImportPayload,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(payload.patient_id)
    authorize_patient(db, user, target, request, write=True, any_resource=True)
    rows = parse_bundle(payload.bundle, target, payload.reason)
    require_clinical_access(
        db, user, target, request, write=True, resource={KIND_RESOURCE[row.data.kind] for row in rows}
    )
    digest = hashlib.sha256(
        json.dumps(payload.bundle, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    source = FHIRImport(patient_id=target, sha256=digest, original=payload.bundle, imported_by=user.id)
    db.add(source)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "This exact bundle was already imported for this patient")
    ids = []
    for row in rows:
        root = HealthRecord(patient_id=target, kind=row.data.kind)
        db.add(root)
        db.flush()
        revision = HealthRevision(
            record_id=root.id,
            version=1,
            title=row.title,
            occurred_on=row.occurred_on,
            data=row.data.model_dump(mode="json"),
            recorded_by=user.id,
            provenance="patient_reported" if user.role == "patient" else "clinician_recorded",
            reason=row.reason,
        )
        db.add(revision)
        db.flush()
        db.add(FHIRImportLink(revision_id=revision.id, import_id=source.id))
        ids.append(root.id)
    audit_service.log_event(
        db,
        "IMPORT_FHIR_SUBSET",
        "fhir",
        actor_id=user.id,
        patient_id=target,
        resource_id=source.id,
        details=f"records={len(ids)}",
        commit=False,
    )
    db.commit()
    return dict(import_id=source.id, sha256=digest, record_ids=ids)


@router.get("/imports/{source_id}")
def get_original(
    source_id: UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    source = db.get(FHIRImport, str(source_id))
    if not source:
        raise HTTPException(404, "Import source not found")
    groups = {"Condition": "diagnoses", "AllergyIntolerance": "allergies", "Observation": "labs"}
    required = {
        groups.get(entry.get("resource", {}).get("resourceType"))
        for entry in source.original.get("entry", [])
        if entry.get("resource", {}).get("resourceType") != "Patient"
    }
    # Original imports can contain several groups; authorization covers the entire source.
    authorize_patient(db, user, source.patient_id, request, resource=required)
    audit_service.log_event(
        db, "VIEW_FHIR_SOURCE", "fhir", actor_id=user.id, patient_id=source.patient_id, resource_id=source.id
    )
    return dict(sha256=source.sha256, original=source.original, created_at=source.created_at)
