from app.core.time import utc_now
from datetime import timedelta
from uuid import UUID
from typing import Literal, Annotated
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from app.core.input_text import safe_text
from sqlalchemy import update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.api.deps import get_db, get_current_user, get_current_patient
from app.models.user import User
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.consent import ConsentGrant
from app.models.access_request import AccessRequest
from app.models.document import MedicalDocument
from app.models.audit import AuditAction, AuditLog
from app.models.operations import Organization
from app.services.organizations import organization_active
from app.services.authorization import verified_doctor, active_grants, SCOPE_TYPES, allowed_clinical_resources
from app.core.clinical_resources import ClinicalResource, CLINICAL_RESOURCES, valid_resources
from app.services.audit_service import audit_service
from app.core.errors import PermissionDeniedException, ResourceNotFoundException

router = APIRouter(prefix="/consent", tags=["Patient consent"])


class AccessRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    _safe_text = field_validator("*", mode="after")(safe_text)
    organization_id: UUID | None = None
    patient_id: UUID | Annotated[str, Field(pattern=r"^[A-Z][0-9]{3}$")]
    scope: Literal["all", "prescriptions_only", "labs_only"]
    purpose: str = Field(min_length=5, max_length=255)
    duration_hours: int = Field(default=24, ge=1, le=720)
    allow_upload: bool = False
    include_clinical_records: bool = False
    allow_clinical_write: bool = False
    clinical_resources: list[ClinicalResource] | None = Field(default=None, min_length=1, max_length=9)

    @model_validator(mode="after")
    def clinical_scope(self):
        if self.include_clinical_records and self.scope != "all":
            raise ValueError("Clinical sharing requires all document categories for source access")
        if self.allow_clinical_write and not self.include_clinical_records:
            raise ValueError("Clinical write permission requires clinical sharing")
        if self.clinical_resources is not None and not self.include_clinical_records:
            raise ValueError("Clinical groups require clinical sharing")
        if self.include_clinical_records:
            selected = (
                set(CLINICAL_RESOURCES)
                if self.clinical_resources is None
                else valid_resources(self.clinical_resources)
            )
            if not selected:
                raise ValueError("Interventions require linked care plans; select valid clinical groups")
            self.clinical_resources = sorted(selected)
        return self

    @field_validator("patient_id", mode="before")
    @classmethod
    def normalize_patient_id(cls, value):
        return value.strip().upper() if isinstance(value, str) else value


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "deny"]
    document_ids: list[UUID] | None = Field(default=None, max_length=200)
    clinical_resources: list[ClinicalResource] | None = Field(default=None, min_length=1, max_length=9)


def request_out(db, item):
    doctor = db.get(Doctor, item.doctor_id)
    organization = db.get(Organization, item.organization_id) if item.organization_id else None
    grant = db.get(ConsentGrant, item.grant_id) if item.grant_id else None
    return {
        "id": item.id,
        "patient_id": item.patient_id,
        "doctor_id": doctor.id,
        "doctor_name": doctor.user.full_name,
        "organization": organization.name if organization else doctor.hospital_affiliation,
        "organization_id": item.organization_id,
        "organization_verified": bool(
            organization and organization_active(db, organization.id, doctor.user_id)
        ),
        "organization_note": "Verified organization membership required on every access"
        if organization
        else "Self-reported affiliation; institution verification is pending",
        "scope": item.scope,
        "purpose": item.purpose,
        "duration_hours": item.duration_hours,
        "allow_upload": item.allow_upload,
        "include_clinical_records": item.include_clinical_records,
        "allow_clinical_write": item.allow_clinical_write,
        "clinical_resources": sorted(valid_resources(item.clinical_resources))
        if item.include_clinical_records
        else [],
        "granted_clinical_resources": sorted(valid_resources(grant.clinical_resources))
        if grant and grant.include_clinical_records
        else None,
        "status": item.status,
        "created_at": item.created_at,
    }


@router.post("/requests", status_code=201)
def create_request(
    payload: AccessRequestIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doctor = verified_doctor(db, user)
    organization_id = str(payload.organization_id) if payload.organization_id else None
    if not organization_active(db, organization_id, user.id):
        raise HTTPException(403, "Active clinician membership in this verified organization required")
    patient = (
        db.get(Patient, str(payload.patient_id))
        if isinstance(payload.patient_id, UUID)
        else db.query(Patient).filter_by(patient_code=payload.patient_id).first()
    )
    if not patient:
        raise HTTPException(400, "Unable to request access for this identifier")
    if (
        db.query(AccessRequest)
        .filter_by(doctor_id=doctor.id, patient_id=patient.id, status="pending")
        .first()
    ):
        raise HTTPException(409, "An access request is already pending")
    item = AccessRequest(
        doctor_id=doctor.id,
        **payload.model_dump(exclude={"patient_id", "organization_id"}),
        patient_id=patient.id,
        organization_id=organization_id,
    )
    db.add(item)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "An access request is already pending")
    audit_service.log_event(
        db,
        "REQUEST_ACCESS",
        "access_request",
        actor_id=user.id,
        patient_id=item.patient_id,
        resource_id=item.id,
    )
    return request_out(db, item)


@router.get("/requests")
def requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    query = db.query(AccessRequest)
    if user.role == "patient":
        query = query.filter_by(patient_id=user.patient_profile.id)
    elif user.role == "doctor":
        query = query.filter_by(doctor_id=verified_doctor(db, user).id)
    else:
        raise PermissionDeniedException()
    return [request_out(db, item) for item in query.order_by(AccessRequest.created_at.desc()).limit(200)]


@router.post("/requests/{request_id}/decision")
def decide(
    request_id: UUID, payload: DecisionIn, ctx=Depends(get_current_patient), db: Session = Depends(get_db)
):
    user, patient = ctx
    item = db.query(AccessRequest).filter_by(id=str(request_id), patient_id=patient.id).first()
    if not item:
        raise ResourceNotFoundException("Access request")
    doctor = db.get(Doctor, item.doctor_id)
    if payload.decision == "approve" and (
        doctor.verification_status != "verified" or not doctor.user.is_active
    ):
        raise HTTPException(409, "Doctor is no longer verified and active")
    if payload.decision == "approve" and not organization_active(db, item.organization_id, doctor.user_id):
        raise HTTPException(409, "Organization verification or clinician membership is no longer active")
    clinical_resources = valid_resources(item.clinical_resources) if item.include_clinical_records else set()
    if payload.decision == "approve" and payload.clinical_resources is not None:
        selected_clinical = valid_resources(payload.clinical_resources)
        if not selected_clinical or not selected_clinical <= clinical_resources:
            raise HTTPException(
                422,
                "Approval may only reduce requested clinical groups; interventions require linked care plans",
            )
        clinical_resources = selected_clinical
    selected = (
        None if payload.document_ids is None else list(dict.fromkeys(str(i) for i in payload.document_ids))
    )
    if selected is not None and payload.decision == "approve":
        count = (
            db.query(MedicalDocument)
            .filter(
                MedicalDocument.id.in_(selected),
                MedicalDocument.patient_id == patient.id,
                MedicalDocument.document_type.in_(SCOPE_TYPES[item.scope]),
            )
            .count()
        )
        if not selected or count != len(selected) or item.allow_upload or item.include_clinical_records:
            raise HTTPException(422, "Selected-record grants cannot permit uploads or share clinical records")
    status = "approved" if payload.decision == "approve" else "denied"
    now = utc_now()
    result = db.execute(
        update(AccessRequest)
        .where(AccessRequest.id == item.id, AccessRequest.status == "pending")
        .values(status=status, decided_at=now)
    )
    if result.rowcount != 1:
        raise HTTPException(409, "Request already decided")
    if status == "approved":
        grant = ConsentGrant(
            patient_id=patient.id,
            doctor_id=item.doctor_id,
            scope=item.scope,
            organization_id=item.organization_id,
            purpose=item.purpose,
            valid_from=now,
            valid_until=now + timedelta(hours=item.duration_hours),
            allow_upload=item.allow_upload,
            document_ids=selected,
            include_clinical_records=item.include_clinical_records,
            clinical_resources=sorted(clinical_resources) if item.include_clinical_records else None,
            allow_clinical_write=item.allow_clinical_write,
        )
        db.add(grant)
        db.flush()
        item.grant_id = grant.id
    audit_service.log_event(
        db,
        AuditAction.GRANT_CONSENT if status == "approved" else "DENY_CONSENT",
        "access_request",
        actor_id=user.id,
        patient_id=patient.id,
        resource_id=item.id,
    )
    return request_out(db, item)


@router.get("/grants")
def grants(ctx=Depends(get_current_patient), db: Session = Depends(get_db)):
    _, patient = ctx
    now = utc_now()
    items = (
        db.query(ConsentGrant)
        .filter_by(patient_id=patient.id)
        .order_by(ConsentGrant.created_at.desc())
        .limit(200)
    )
    return [
        {
            "id": g.id,
            "doctor_name": g.doctor.user.full_name,
            "scope": g.scope,
            "purpose": g.purpose,
            "valid_until": g.valid_until,
            "is_revoked": g.is_revoked,
            "allow_upload": g.allow_upload,
            "document_ids": g.document_ids,
            "include_clinical_records": g.include_clinical_records,
            "allow_clinical_write": g.allow_clinical_write,
            "clinical_resources": sorted(valid_resources(g.clinical_resources))
            if g.include_clinical_records
            else [],
            "organization_id": g.organization_id,
            "active": not g.is_revoked
            and g.valid_from <= now < g.valid_until
            and g.doctor.verification_status == "verified"
            and g.doctor.user.is_active
            and organization_active(db, g.organization_id, g.doctor.user_id),
        }
        for g in items
    ]


@router.post("/grants/{grant_id}/revoke", status_code=204)
def revoke(grant_id: UUID, ctx=Depends(get_current_patient), db: Session = Depends(get_db)):
    user, patient = ctx
    grant = db.query(ConsentGrant).filter_by(id=str(grant_id), patient_id=patient.id).first()
    if not grant:
        raise ResourceNotFoundException("Consent grant")
    if not grant.is_revoked:
        grant.is_revoked = True
        grant.revoked_at = utc_now()
        audit_service.log_event(
            db,
            AuditAction.REVOKE_CONSENT,
            "consent_grant",
            actor_id=user.id,
            patient_id=patient.id,
            resource_id=grant.id,
        )


@router.get("/patients")
def authorized_patients(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doctor = verified_doctor(db, user)
    grants = active_grants(db, doctor.id)
    ids = {g.patient_id for g in grants}
    return [
        {
            "id": p.id,
            "full_name": p.user.full_name,
            "clinical_read": bool(allowed_clinical_resources(db, user, p.id)),
            "clinical_write": bool(allowed_clinical_resources(db, user, p.id, write=True)),
            "clinical_read_resources": sorted(allowed_clinical_resources(db, user, p.id)),
            "clinical_write_resources": sorted(allowed_clinical_resources(db, user, p.id, write=True)),
            "upload_types": sorted(
                set().union(
                    *(
                        SCOPE_TYPES[g.scope]
                        for g in grants
                        if g.patient_id == p.id and g.allow_upload and g.document_ids is None
                    )
                )
            ),
        }
        for p in db.query(Patient).filter(Patient.id.in_(ids))
    ]


@router.get("/audit")
def history(ctx=Depends(get_current_patient), db: Session = Depends(get_db)):
    _, patient = ctx
    events = (
        db.query(AuditLog).filter_by(patient_id=patient.id).order_by(AuditLog.created_at.desc()).limit(200)
    )
    return [
        {
            "id": e.id,
            "action": e.action,
            "actor_id": e.actor_id,
            "actor_name": db.get(User, e.actor_id).full_name
            if e.actor_id and db.get(User, e.actor_id)
            else "System",
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "created_at": e.created_at,
        }
        for e in events
    ]
