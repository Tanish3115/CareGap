from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import get_db
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.database import Base, engine
import app.models  # Ensures all models are registered
from app.api.auth import router as auth_router
from app.api.documents import router as documents_router
from app.api.patients import router as patients_router
from app.api.consent import router as consent_router
from app.api.admin import router as admin_router
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


@app.middleware("http")
async def security_headers(request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        origin = request.headers.get("origin")
        if origin and origin not in settings.CORS_ORIGINS:
            return JSONResponse({"detail": "Cross-site request rejected"}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
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


@app.get("/health")
@app.get(f"{settings.API_V1_PREFIX}/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


@app.get("/ready")
def readiness(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT version_num FROM alembic_version"))
        return {"status": "ready"}
    except Exception:
        return JSONResponse({"status": "not_ready"}, status_code=503)

