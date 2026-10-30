from app.core.time import utc_now
from typing import Annotated, Generator
from fastapi import Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import decode_access_token
from app.core.errors import CredentialsException, PermissionDeniedException
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.session import AuthSession
from datetime import datetime
from app.config import settings

bearer_scheme = HTTPBearer(auto_error=False)


def session_token(request: Request):
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    return value if scheme.lower() == "bearer" and value else request.cookies.get("caregap_session")


def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    token = session_token(request)
    if not token:
        raise CredentialsException("Authentication token missing")

    if request.method not in ("GET", "HEAD", "OPTIONS") and request.cookies.get("caregap_session"):
        origin = request.headers.get("origin")
        if (origin and origin not in settings.CORS_ORIGINS) or request.headers.get("sec-fetch-site") == "cross-site":
            raise PermissionDeniedException("Cross-site request rejected")

    payload = decode_access_token(token)
    if not payload or "sub" not in payload or "jti" not in payload:
        raise CredentialsException("Invalid or expired authentication token")

    session = db.get(AuthSession, payload["jti"])
    if not session or session.user_id != payload["sub"] or session.revoked_at or session.expires_at <= utc_now():
        raise CredentialsException("Session expired or revoked")

    user_id: str = payload["sub"]
    user = db.query(User).filter(User.id == user_id).first()
    if not user or not user.is_active:
        raise CredentialsException("User account not found or deactivated")

    return user


def require_role(required_role: UserRole):
    def role_checker(current_user: Annotated[User, Depends(get_current_user)]) -> User:
        if current_user.role != required_role.value:
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
