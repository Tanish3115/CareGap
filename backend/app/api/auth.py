from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.core.security import hash_password, verify_password, create_access_token
from app.core.errors import CredentialsException
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.doctor import Doctor, DoctorVerificationStatus
from app.models.audit import AuditAction
from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserOut
from app.services.audit_service import audit_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register_user(payload: UserRegister, request: Request, db: Session = Depends(get_db)):
    """Register a new user (Patient, Doctor, or Admin) with their corresponding profile."""
    existing_user = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email address already exists",
        )

    # Create root User entity
    new_user = User(
        email=payload.email.lower(),
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
        phone=payload.phone,
    )
    db.add(new_user)
    db.flush()  # Generate ID

    # Create specific role profile
    if payload.role == UserRole.PATIENT.value:
        patient_profile = Patient(
            user_id=new_user.id,
            gender=payload.gender,
            blood_group=payload.blood_group,
            emergency_contact=payload.emergency_contact,
        )
        db.add(patient_profile)
    elif payload.role == UserRole.DOCTOR.value:
        if not payload.license_number or not payload.specialization:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Doctor registration requires license_number and specialization",
            )
        # Check license uniqueness
        existing_doc = db.query(Doctor).filter(Doctor.license_number == payload.license_number).first()
        if existing_doc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A doctor with this license number already exists",
            )
        doctor_profile = Doctor(
            user_id=new_user.id,
            license_number=payload.license_number,
            specialization=payload.specialization,
            hospital_affiliation=payload.hospital_affiliation,
            verification_status=DoctorVerificationStatus.PENDING.value,
        )
        db.add(doctor_profile)

    db.commit()
    db.refresh(new_user)

    client_ip = request.client.host if request.client else None
    audit_service.log_event(
        db=db,
        action=AuditAction.REGISTER,
        resource_type="user",
        actor_id=new_user.id,
        resource_id=new_user.id,
        ip_address=client_ip,
        details=f"User registered with role: {new_user.role}",
    )

    return new_user


@router.post("/login", response_model=TokenResponse)
def login_user(payload: UserLogin, request: Request, db: Session = Depends(get_db)):
    """Authenticate with email and password to receive a JWT access token."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    client_ip = request.client.host if request.client else None

    if not user or not verify_password(payload.password, user.hashed_password):
        audit_service.log_event(
            db=db,
            action=AuditAction.UNAUTHORIZED_ACCESS_ATTEMPT,
            resource_type="auth",
            ip_address=client_ip,
            details=f"Failed login attempt for email: {payload.email}",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Please contact support.",
        )

    token = create_access_token(
        data={"sub": user.id, "email": user.email, "role": user.role}
    )

    audit_service.log_event(
        db=db,
        action=AuditAction.LOGIN,
        resource_type="auth",
        actor_id=user.id,
        ip_address=client_ip,
        details="User logged in successfully",
    )

    return TokenResponse(
        access_token=token,
        token_type="bearer",
        role=user.role,
        user_id=user.id,
        full_name=user.full_name,
        email=user.email,
    )


@router.get("/me")
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current authenticated user info including patient or doctor profile."""
    profile_data = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "phone": current_user.phone,
        "is_active": current_user.is_active,
    }

    if current_user.role == UserRole.PATIENT.value and current_user.patient_profile:
        profile_data["patient"] = {
            "id": current_user.patient_profile.id,
            "date_of_birth": current_user.patient_profile.date_of_birth,
            "gender": current_user.patient_profile.gender,
            "blood_group": current_user.patient_profile.blood_group,
            "emergency_contact": current_user.patient_profile.emergency_contact,
            "address": current_user.patient_profile.address,
            "abha_id": current_user.patient_profile.abha_id,
        }
    elif current_user.role == UserRole.DOCTOR.value and current_user.doctor_profile:
        profile_data["doctor"] = {
            "id": current_user.doctor_profile.id,
            "license_number": current_user.doctor_profile.license_number,
            "specialization": current_user.doctor_profile.specialization,
            "hospital_affiliation": current_user.doctor_profile.hospital_affiliation,
            "verification_status": current_user.doctor_profile.verification_status,
        }

    return profile_data

