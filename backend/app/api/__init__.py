from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.patients import router as patients_router

__all__ = ["auth_router", "documents_router", "patients_router"]

