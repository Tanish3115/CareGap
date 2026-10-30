from app.core.time import utc_now
from fastapi import APIRouter, Depends, HTTPException, status
from datetime import datetime
from app.models.consent import ConsentGrant
from app.services.audit_service import audit_service
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_patient
from app.models.user import User
from app.models.patient import Patient
from app.models.document import MedicalDocument, DocumentType
from app.schemas.patient import PatientProfile, PatientProfileUpdate

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.get("/me", response_model=PatientProfile)
def get_my_patient_profile(
    patient_ctx: tuple[User, Patient] = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Retrieve full longitudinal profile for the authenticated patient."""
    user, patient = patient_ctx
    audit_service.log_event(db, "VIEW_RECORD", "patient_profile", actor_id=user.id, patient_id=patient.id)
    return PatientProfile(
        id=patient.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        blood_group=patient.blood_group,
        emergency_contact=patient.emergency_contact,
        address=patient.address,
        abha_id=patient.abha_id,
        created_at=patient.created_at,
    )


@router.put("/me", response_model=PatientProfile)
def update_my_patient_profile(
    payload: PatientProfileUpdate,
    patient_ctx: tuple[User, Patient] = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Update editable patient demographic and emergency information."""
    user, patient = patient_ctx

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(patient, field, value)

    audit_service.log_event(db, "UPDATE_PROFILE", "patient_profile", actor_id=user.id, patient_id=patient.id)
    db.refresh(patient)

    return PatientProfile(
        id=patient.id,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        date_of_birth=patient.date_of_birth,
        gender=patient.gender,
        blood_group=patient.blood_group,
        emergency_contact=patient.emergency_contact,
        address=patient.address,
        abha_id=patient.abha_id,
        created_at=patient.created_at,
    )


@router.get("/summary/stats")
def get_patient_summary_stats(
    patient_ctx: tuple[User, Patient] = Depends(get_current_patient),
    db: Session = Depends(get_db),
):
    """Return dashboard summary KPIs for the patient."""
    user, patient = patient_ctx

    total_docs = db.query(MedicalDocument).filter(MedicalDocument.patient_id == patient.id).count()
    prescriptions_count = (
        db.query(MedicalDocument)
        .filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == DocumentType.PRESCRIPTION.value,
        )
        .count()
    )
    labs_count = (
        db.query(MedicalDocument)
        .filter(
            MedicalDocument.patient_id == patient.id,
            MedicalDocument.document_type == DocumentType.LAB_REPORT.value,
        )
        .count()
    )

    return {
        "total_documents": total_docs,
        "prescriptions_count": prescriptions_count,
        "lab_reports_count": labs_count,
        "pending_care_gaps": None,
        "active_doctor_grants": db.query(ConsentGrant).filter(
            ConsentGrant.patient_id == patient.id, ConsentGrant.is_revoked.is_(False),
            ConsentGrant.valid_from <= utc_now(), ConsentGrant.valid_until > utc_now(),
            ConsentGrant.scope.in_(["all", "prescriptions_only", "labs_only"])).count(),
    }

