from typing import Annotated, Generator
from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import decode_access_token
from app.core.errors import CredentialsException, PermissionDeniedException
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.doctor import Doctor

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    if not token:
        raise CredentialsException("Authentication token missing")

    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise CredentialsException("Invalid or expired authentication token")

    user_id: str = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise CredentialsException("User account not found or deactivated")

    return user


def require_role(required_role: UserRole):
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role != required_role.value and current_user.role != UserRole.ADMIN.value:
            raise PermissionDeniedException(f"Requires {required_role.value} privilege")
        return current_user
    return role_checker


def get_current_patient(
    current_user: Annotated[User, Depends(require_role(UserRole.PATIENT))],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[User, Patient]:
    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise PermissionDeniedException("User does not have an active patient profile")
    return current_user, patient


def get_current_doctor(
    current_user: Annotated[User, Depends(require_role(UserRole.DOCTOR))],
    db: Annotated[Session, Depends(get_db)],
) -> tuple[User, Doctor]:
    doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
    if not doctor:
        raise PermissionDeniedException("User does not have an active doctor profile")
    return current_user, doctor
