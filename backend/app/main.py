from app.api.summary_assistance import router as summary_assistance_router
from contextlib import asynccontextmanager
import logging
from uuid import uuid4
from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import engine
import app.models  # Ensures all models are registered
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.patients import router as patients_router
from app.api.consent import router as consent_router
from app.api.admin import router as admin_router
from app.api.clinical import router as clinical_router
from app.api.document_reviews import router as document_reviews_router
from app.api.prescriptions import router as prescriptions_router
from app.api.medication_use import router as medication_use_router
from app.api.health_records import router as health_records_router
from app.api.coordination import router as coordination_router
from app.api.decision_support import router as decision_support_router
from app.api.interoperability import router as interoperability_router
from app.api.operations import router as operations_router
from app.api.privacy_export import router as privacy_export_router
from app.api.unified_timeline import router as unified_timeline_router
from app.api.deletions import router as deletions_router
from app.core.limiter import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.core.request_limits import RequestSizeLimit
from starlette.responses import JSONResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ENVIRONMENT == "production" and not settings.COOKIE_SECURE:
        raise RuntimeError("Production requires secure session cookies and HTTPS")
    if settings.ENVIRONMENT == "production" and not settings.LOCAL_VOLUME_ENCRYPTION_VERIFIED:
        with engine.connect() as connection:
            if connection.execute(
                text("SELECT count(*) FROM medical_documents WHERE storage_backend='local'")
            ).scalar_one():
                raise RuntimeError(
                    "Existing local documents require verified encrypted volumes before production startup"
                )
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="CareGap 360 - AI-Powered Unified Health Records, Medication Intelligence & Care Continuity Platform",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(RequestSizeLimit, max_bytes=settings.MAX_FILE_SIZE_BYTES + 65536)


@app.exception_handler(RequestValidationError)
async def private_validation_error(_request, _exception):
    # Pydantic errors can echo passwords, clinical input, dictionary keys and
    # custom-validator messages. Keep the existing detail[].msg client contract
    # without copying any part of the submitted error or request body.
    return JSONResponse(
        status_code=422,
        content={
            "detail": [
                {
                    "type": "request_validation_error",
                    "loc": ["request"],
                    "msg": "Request failed. Please try again.",
                }
            ]
        },
    )


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in settings.CORS_ORIGINS:
            return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)
    request_id = str(uuid4())
    try:
        response = await call_next(request)
    except Exception:
        # Exception values, URLs and tracebacks may contain source text or identifiers.
        logging.getLogger("caregap.requests").error("Unhandled request failure request_id=%s", request_id)
        response = JSONResponse({"detail": "Operation failed"}, status_code=500)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = request_id
    return response


# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(documents_router, prefix=settings.API_V1_PREFIX)
app.include_router(patients_router, prefix=settings.API_V1_PREFIX)
app.include_router(consent_router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_router, prefix=settings.API_V1_PREFIX)
app.include_router(clinical_router, prefix=settings.API_V1_PREFIX)
app.include_router(document_reviews_router, prefix=settings.API_V1_PREFIX)
app.include_router(prescriptions_router, prefix=settings.API_V1_PREFIX)
app.include_router(medication_use_router, prefix=settings.API_V1_PREFIX)
app.include_router(health_records_router, prefix=settings.API_V1_PREFIX)
app.include_router(coordination_router, prefix=settings.API_V1_PREFIX)
app.include_router(decision_support_router, prefix=settings.API_V1_PREFIX)
app.include_router(interoperability_router, prefix=settings.API_V1_PREFIX)
app.include_router(operations_router, prefix=settings.API_V1_PREFIX)
app.include_router(privacy_export_router, prefix=settings.API_V1_PREFIX)
app.include_router(unified_timeline_router, prefix=settings.API_V1_PREFIX)
app.include_router(summary_assistance_router, prefix=settings.API_V1_PREFIX)
app.include_router(deletions_router, prefix=settings.API_V1_PREFIX)


@app.get("/health")
@app.get(f"{settings.API_V1_PREFIX}/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "demo_mode": settings.DEMO_MODE,
    }


@app.get("/ready")
def readiness(db: Session = Depends(get_db)):
    try:
        if db.execute(text("SELECT version_num FROM alembic_version")).scalar_one() != "0019":
            return JSONResponse({"status": "schema_not_ready"}, status_code=503)
        if settings.ENVIRONMENT == "production" and not limiter._storage.check():
            return JSONResponse({"status": "rate_store_not_ready"}, status_code=503)
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)
