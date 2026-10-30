from app.core.time import utc_now
"""One deny-by-default policy for clinical access across API handlers."""
from datetime import datetime
from app.models.user import UserRole
from app.models.doctor import Doctor, DoctorVerificationStatus
from app.models.patient import Patient
from app.models.consent import ConsentGrant
from app.models.audit import AuditAction
from app.core.errors import PermissionDeniedException
from app.services.audit_service import audit_service
from sqlalchemy import and_, or_, true
from app.models.document import MedicalDocument

SCOPE_TYPES = {"all": {"prescription", "lab_report", "discharge_summary", "referral", "scan", "other"},
               "prescriptions_only": {"prescription"}, "labs_only": {"lab_report"}}


def active_grants(db, doctor_id, patient_id=None):
    now = utc_now()
    query = db.query(ConsentGrant).filter(
        ConsentGrant.doctor_id == doctor_id, ConsentGrant.is_revoked.is_(False),
        ConsentGrant.valid_from <= now, ConsentGrant.valid_until > now,
        ConsentGrant.scope.in_(SCOPE_TYPES))
    if patient_id:
        query = query.filter(ConsentGrant.patient_id == patient_id)
    return query.all()


def verified_doctor(db, user):
    doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
    if user.role != UserRole.DOCTOR.value or not doctor or doctor.verification_status != DoctorVerificationStatus.VERIFIED.value:
        raise PermissionDeniedException("Verified doctor status required")
    return doctor


def permitted_types(db, user, patient_id, request=None, action="read"):
    if user.role == UserRole.PATIENT.value:
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if patient and patient.id == patient_id:
            return SCOPE_TYPES["all"]
    elif user.role == UserRole.DOCTOR.value:
        doctor = verified_doctor(db, user)
        grants = active_grants(db, doctor.id, patient_id)
        if action == "upload":
            grants = [g for g in grants if g.allow_upload and g.document_ids is None]
        if grants:
            return set().union(*(SCOPE_TYPES[g.scope] for g in grants))
    audit_service.log_event(db, AuditAction.UNAUTHORIZED_ACCESS_ATTEMPT, "clinical_access",
                            actor_id=user.id, patient_id=patient_id,
                            ip_address=request.client.host if request and request.client else None)
    raise PermissionDeniedException("You are not authorized: no active consent grant or patient ownership")


def can_view_document(db, user, document):
    if user.role == "patient":
        return user.patient_profile and user.patient_profile.id == document.patient_id
    if user.role != "doctor":
        return False
    doctor = verified_doctor(db, user)
    return any(document.document_type in SCOPE_TYPES[g.scope] and
               (g.document_ids is None or document.id in g.document_ids)
               for g in active_grants(db, doctor.id, document.patient_id))


def document_filter(db, user, patient_id):
    if user.role == "patient":
        return true()
    doctor = verified_doctor(db, user)
    clauses = []
    for grant in active_grants(db, doctor.id, patient_id):
        clause = MedicalDocument.document_type.in_(SCOPE_TYPES[grant.scope])
        if grant.document_ids is not None:
            clause = and_(clause, MedicalDocument.id.in_(grant.document_ids))
        clauses.append(clause)
    return or_(*clauses) if clauses else MedicalDocument.id.in_([])


def require_document_access(db, user, document, request):
    if not can_view_document(db, user, document):
        audit_service.log_event(db, AuditAction.UNAUTHORIZED_ACCESS_ATTEMPT, "document",
                                actor_id=user.id, patient_id=document.patient_id, resource_id=document.id)
        raise PermissionDeniedException("You are not authorized to access this document type")
