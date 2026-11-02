from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from app.core.input_text import safe_text
from sqlalchemy import func, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db, require_role
from app.core.time import utc_now
from app.models.user import User, UserRole
from app.models.session import AuthSession
from app.models.doctor import Doctor
from app.models.consent import ConsentGrant
from app.models.operations import Organization, OrganizationMembership, OrganizationHistory, PrivacyRequest
from app.services.audit_service import audit_service

router = APIRouter(tags=["Organization operations and privacy requests"])
admin_dep = require_role(UserRole.ADMIN)
Evidence = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    _safe_text = field_validator("*", mode="after")(safe_text)


class OrgInput(Strict):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    status: Literal["pending", "verified", "inactive"]
    expected_version: int = Field(ge=0)
    evidence: Evidence


class MemberInput(Strict):
    user_id: UUID
    role: Literal["clinician", "staff"]
    status: Literal["active", "inactive"]
    expected_version: int = Field(ge=0)
    evidence: Evidence


class Activation(Strict):
    expected_active: bool
    active: bool
    evidence: Evidence


class PrivacyInput(Strict):
    kind: Literal["export", "correction", "erasure"]


class PrivacyDecision(Strict):
    expected_version: int = Field(ge=1)
    status: Literal["under_review", "closed"]
    decision_reference: Evidence


def org_out(org):
    return dict(id=org.id, name=org.name, status=org.status, version=org.version, evidence=org.evidence)


@router.get("/admin/organizations")
def organizations(
    admin=Depends(admin_dep),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return [
        org_out(org)
        for org in db.query(Organization)
        .order_by(Organization.name, Organization.id)
        .offset(offset)
        .limit(limit)
    ]


@router.post("/admin/organizations", status_code=201)
def create_org(payload: OrgInput, admin=Depends(admin_dep), db: Session = Depends(get_db)):
    if payload.expected_version != 0:
        raise HTTPException(409, "New organization requires version zero")
    org = Organization(name=payload.name, status=payload.status, evidence=payload.evidence)
    db.add(org)
    db.flush()
    db.add(
        OrganizationHistory(
            organization_id=org.id,
            actor_id=admin.id,
            change=dict(name=org.name, status=org.status, version=1, evidence=org.evidence),
        )
    )
    audit_service.log_event(db, "CREATE_ORGANIZATION", "organization", actor_id=admin.id, resource_id=org.id)
    return org_out(org)


@router.put("/admin/organizations/{org_id}")
def update_org(org_id: UUID, payload: OrgInput, admin=Depends(admin_dep), db: Session = Depends(get_db)):
    changed = db.execute(
        update(Organization)
        .where(Organization.id == str(org_id), Organization.version == payload.expected_version)
        .values(
            name=payload.name,
            status=payload.status,
            evidence=payload.evidence,
            version=payload.expected_version + 1,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Organization changed or is missing. Reload before saving.")
    if payload.status != "verified":
        db.execute(
            update(ConsentGrant)
            .where(ConsentGrant.organization_id == str(org_id), ConsentGrant.is_revoked.is_(False))
            .values(is_revoked=True, revoked_at=utc_now())
        )
    db.add(
        OrganizationHistory(
            organization_id=str(org_id),
            actor_id=admin.id,
            change=dict(
                name=payload.name,
                status=payload.status,
                version=payload.expected_version + 1,
                evidence=payload.evidence,
            ),
        )
    )
    audit_service.log_event(
        db, "UPDATE_ORGANIZATION", "organization", actor_id=admin.id, resource_id=str(org_id)
    )
    return org_out(db.get(Organization, str(org_id)))


@router.get("/admin/organizations/{org_id}/history")
def org_history(
    org_id: UUID,
    admin=Depends(admin_dep),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return [
        dict(change=row.change, created_at=row.created_at)
        for row in db.query(OrganizationHistory)
        .filter_by(organization_id=str(org_id))
        .order_by(OrganizationHistory.created_at.desc(), OrganizationHistory.id)
        .offset(offset)
        .limit(limit)
    ]


@router.get("/admin/organizations/{org_id}/members")
def members(
    org_id: UUID,
    admin=Depends(admin_dep),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    rows = (
        db.query(OrganizationMembership, User)
        .join(User, User.id == OrganizationMembership.user_id)
        .filter(OrganizationMembership.organization_id == str(org_id))
        .order_by(User.full_name, User.id)
        .offset(offset)
        .limit(limit)
    )
    return [
        dict(
            user_id=user.id,
            name=user.full_name,
            role=member.role,
            status=member.status,
            version=member.version,
        )
        for member, user in rows
    ]


@router.put("/admin/organizations/{org_id}/members")
def set_member(org_id: UUID, payload: MemberInput, admin=Depends(admin_dep), db: Session = Depends(get_db)):
    org = db.get(Organization, str(org_id))
    user = db.get(User, str(payload.user_id))
    if not org or not user:
        raise HTTPException(404, "Organization or user not found")
    if payload.status == "active" and not user.is_active:
        raise HTTPException(422, "Inactive users cannot have active memberships")
    if payload.role == "clinician" and payload.status == "active":
        doctor = db.query(Doctor).filter_by(user_id=user.id, verification_status="verified").first()
        if not doctor:
            raise HTTPException(422, "Clinician membership requires a verified doctor account")
    if payload.expected_version == 0:
        db.add(
            OrganizationMembership(
                organization_id=org.id, user_id=user.id, role=payload.role, status=payload.status
            )
        )
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Membership already exists. Reload before saving.")
    else:
        changed = db.execute(
            update(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == org.id,
                OrganizationMembership.user_id == user.id,
                OrganizationMembership.version == payload.expected_version,
            )
            .values(role=payload.role, status=payload.status, version=payload.expected_version + 1)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Membership changed. Reload before saving.")
    db.add(
        OrganizationHistory(
            organization_id=org.id,
            actor_id=admin.id,
            change=dict(
                user_id=user.id,
                role=payload.role,
                status=payload.status,
                member_version=payload.expected_version + 1,
                evidence=payload.evidence,
            ),
        )
    )
    if payload.status != "active" or payload.role != "clinician":
        doctor = db.query(Doctor).filter_by(user_id=user.id).first()
        if doctor:
            db.execute(
                update(ConsentGrant)
                .where(
                    ConsentGrant.organization_id == org.id,
                    ConsentGrant.doctor_id == doctor.id,
                    ConsentGrant.is_revoked.is_(False),
                )
                .values(is_revoked=True, revoked_at=utc_now())
            )
    audit_service.log_event(
        db, "SET_ORGANIZATION_MEMBERSHIP", "organization", actor_id=admin.id, resource_id=org.id
    )
    return dict(user_id=user.id, version=payload.expected_version + 1, status=payload.status)


@router.get("/organizations/mine")
def mine(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = (
        db.query(Organization, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.organization_id == Organization.id)
        .filter(
            OrganizationMembership.user_id == user.id,
            OrganizationMembership.status == "active",
            Organization.status == "verified",
        )
        .order_by(Organization.name)
        .limit(100)
    )
    return [dict(id=org.id, name=org.name, role=member.role) for org, member in rows]


@router.get("/admin/users")
def users(
    admin=Depends(admin_dep),
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return [
        dict(id=user.id, name=user.full_name, email=user.email, role=user.role, active=user.is_active)
        for user in db.query(User).order_by(User.created_at, User.id).offset(offset).limit(limit)
    ]


@router.put("/admin/users/{user_id}/activation")
def activation(user_id: UUID, payload: Activation, admin=Depends(admin_dep), db: Session = Depends(get_db)):
    target = db.get(User, str(user_id))
    if not target:
        raise HTTPException(404, "User not found")
    if target.role == "admin" or target.id == admin.id:
        raise HTTPException(403, "Administrator lifecycle is CLI-managed; self-deactivation is prohibited")
    if target.role == "patient" and not target.patient_profile:
        raise HTTPException(409, "An erased or incomplete patient account cannot be reactivated")
    changed = db.execute(
        update(User)
        .where(User.id == target.id, User.is_active == payload.expected_active)
        .values(is_active=payload.active, updated_at=utc_now())
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Account changed. Reload before saving.")
    if not payload.active:
        db.execute(
            update(AuthSession)
            .where(AuthSession.user_id == target.id, AuthSession.revoked_at.is_(None))
            .values(revoked_at=utc_now())
        )
    audit_service.log_event(db, "CHANGE_USER_ACTIVATION", "user", actor_id=admin.id, resource_id=target.id)
    return dict(id=target.id, active=payload.active, sessions_revoked=not payload.active)


@router.get("/admin/metrics")
def metrics(admin=Depends(admin_dep), db: Session = Depends(get_db)):
    # Aggregates only; no clinical values, document names or patient lists.
    from app.models.processing import DocumentProcessingJob

    return dict(
        users=db.query(User).count(),
        active_users=db.query(User).filter_by(is_active=True).count(),
        organizations=db.query(Organization).count(),
        processing=dict(
            db.query(DocumentProcessingJob.status, func.count()).group_by(DocumentProcessingJob.status).all()
        ),
    )


def privacy_out(row):
    return dict(
        id=row.id,
        kind=row.kind,
        status=row.status,
        version=row.version,
        created_at=row.created_at,
        decision_reference=row.decision_reference,
    )


@router.post("/privacy/requests", status_code=201)
def privacy_create(
    payload: PrivacyInput, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if user.role != "patient":
        raise HTTPException(403, "Patient account required")
    row = PrivacyRequest(user_id=user.id, kind=payload.kind)
    db.add(row)
    db.flush()
    audit_service.log_event(
        db,
        "CREATE_PRIVACY_REQUEST",
        "privacy_request",
        actor_id=user.id,
        patient_id=user.patient_profile.id,
        resource_id=row.id,
    )
    return privacy_out(row)


@router.get("/privacy/requests")
def privacy_list(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    if user.role != "patient":
        raise HTTPException(403, "Patient account required")
    return [
        privacy_out(row)
        for row in db.query(PrivacyRequest)
        .filter_by(user_id=user.id)
        .order_by(PrivacyRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
    ]


@router.get("/admin/privacy-requests")
def privacy_queue(
    admin=Depends(admin_dep),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    return [
        privacy_out(row)
        for row in db.query(PrivacyRequest)
        .order_by(PrivacyRequest.created_at.desc())
        .offset(offset)
        .limit(limit)
    ]


@router.put("/admin/privacy-requests/{request_id}")
def privacy_decide(
    request_id: UUID, payload: PrivacyDecision, admin=Depends(admin_dep), db: Session = Depends(get_db)
):
    changed = db.execute(
        update(PrivacyRequest)
        .where(
            PrivacyRequest.id == str(request_id),
            PrivacyRequest.version == payload.expected_version,
            PrivacyRequest.status != "closed",
        )
        .values(
            status=payload.status,
            version=payload.expected_version + 1,
            decision_reference=payload.decision_reference,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Privacy request changed or is already closed")
    audit_service.log_event(
        db, "REVIEW_PRIVACY_REQUEST", "privacy_request", actor_id=admin.id, resource_id=str(request_id)
    )
    return privacy_out(db.get(PrivacyRequest, str(request_id)))
