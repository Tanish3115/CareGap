from uuid import UUID
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.api.deps import require_role, get_db
from app.models.user import UserRole
from app.models.doctor import Doctor
from app.models.audit import AuditLog
from app.models.verification import DoctorVerification
from app.services.audit_service import audit_service

router = APIRouter(prefix="/admin", tags=["Operational administration"])


class VerificationIn(BaseModel):
    status: Literal["verified", "rejected", "pending"]
    evidence_reference: str = Field(min_length=5, max_length=500)


@router.get("/doctors")
def doctors(admin=Depends(require_role(UserRole.ADMIN)), db: Session = Depends(get_db)):
    return [{"id": d.id, "full_name": d.user.full_name, "license_number": d.license_number,
             "specialization": d.specialization, "hospital_affiliation": d.hospital_affiliation,
             "verification_status": d.verification_status} for d in db.query(Doctor).limit(200)]


@router.post("/doctors/{doctor_id}/verification")
def verify(doctor_id: UUID, payload: VerificationIn, admin=Depends(require_role(UserRole.ADMIN)), db: Session = Depends(get_db)):
    doctor = db.get(Doctor, str(doctor_id))
    if not doctor:
        raise HTTPException(404, "Doctor not found")
    if doctor.user_id == admin.id:
        raise HTTPException(403, "Self verification is prohibited")
    doctor.verification_status = payload.status
    db.add(DoctorVerification(doctor_id=doctor.id, reviewer_id=admin.id, status=payload.status,
                              evidence_reference=payload.evidence_reference))
    audit_service.log_event(db, "VERIFY_DOCTOR", "doctor", actor_id=admin.id, resource_id=doctor.id)
    return {"id": doctor.id, "verification_status": doctor.verification_status}


@router.get("/audit")
def audit(admin=Depends(require_role(UserRole.ADMIN)), db: Session = Depends(get_db)):
    # Operational metadata only: no clinical details or document names.
    return [{"id": e.id, "action": e.action, "resource_type": e.resource_type, "created_at": e.created_at}
            for e in db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200)]
