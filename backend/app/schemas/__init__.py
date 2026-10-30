from app.schemas.auth import UserRegister, UserLogin, TokenResponse, UserOut
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.schemas.patient import PatientProfile, PatientProfileUpdate

__all__ = [
    "UserRegister",
    "UserLogin",
    "TokenResponse",
    "UserOut",
    "DocumentResponse",
    "DocumentUploadResponse",
    "PatientProfile",
    "PatientProfileUpdate",
]

