from fastapi import APIRouter, Depends, HTTPException, status
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
):
    """Retrieve full longitudinal profile for the authenticated patient."""
    user, patient = patient_ctx
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

    if payload.date_of_birth is not None:
        patient.date_of_birth = payload.date_of_birth
    if payload.gender is not None:
        patient.gender = payload.gender
    if payload.blood_group is not None:
        patient.blood_group = payload.blood_group
    if payload.emergency_contact is not None:
        patient.emergency_contact = payload.emergency_contact
    if payload.address is not None:
        patient.address = payload.address
    if payload.abha_id is not None:
        patient.abha_id = payload.abha_id

    db.commit()
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
        "pending_care_gaps": 0,
        "active_doctor_grants": len(patient.consent_grants),
    }

