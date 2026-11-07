from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_current_patient, get_db
from app.api.clinical import authorize_patient
from app.config import settings
from app.core.time import utc_now
from app.models.ai_processing import SummaryProcessingConsent
from app.models.user import User
from app.services.authorization import allowed_clinical_resources
from app.services.audit_service import audit_service
from app.services.clinical_summary import summary
from app.services.summary_provider import provider_status, select_sources, ProviderUnavailable

router = APIRouter(tags=["Patient-controlled source selection assistance"])


class ConsentInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    enabled: bool
    provider_reference: str = Field(min_length=3, max_length=200, pattern=r"^[^\x00]*$")


class SummaryInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    patient_id: UUID
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=10, ge=1, le=10)


def consent_out(row):
    return dict(
        version=row.version if row else 0,
        enabled=row.enabled if row else False,
        provider_reference=row.provider_reference if row else settings.SUMMARY_PROVIDER_REFERENCE,
        current_provider_reference=settings.SUMMARY_PROVIDER_REFERENCE,
    )


@router.get("/clinical/summary-assistance/status")
def status(user: User = Depends(get_current_user)):
    return provider_status()


@router.get("/privacy/summary-processing")
def preference(ctx=Depends(get_current_patient), db: Session = Depends(get_db)):
    _, patient = ctx
    return consent_out(db.get(SummaryProcessingConsent, patient.id))


@router.put("/privacy/summary-processing")
def set_preference(payload: ConsentInput, ctx=Depends(get_current_patient), db: Session = Depends(get_db)):
    user, patient = ctx
    if payload.enabled and (
        settings.SUMMARY_PROVIDER != "http"
        or not settings.SUMMARY_PROVIDER_APPROVED
        or payload.provider_reference != settings.SUMMARY_PROVIDER_REFERENCE
    ):
        raise HTTPException(
            422, "An approved named processor must be configured before enabling source processing"
        )
    values = dict(
        enabled=payload.enabled, provider_reference=payload.provider_reference, updated_at=utc_now()
    )
    if payload.expected_version == 0:
        db.add(SummaryProcessingConsent(patient_id=patient.id, version=1, **values))
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409, "Processing preferences changed. Reload before saving.")
    else:
        changed = db.execute(
            update(SummaryProcessingConsent)
            .where(
                SummaryProcessingConsent.patient_id == patient.id,
                SummaryProcessingConsent.version == payload.expected_version,
            )
            .values(version=payload.expected_version + 1, **values)
            .execution_options(synchronize_session=False)
        )
        if changed.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Processing preferences changed. Reload before saving.")
    audit_service.log_event(
        db, "SET_SUMMARY_PROCESSING_CONSENT", "processing_preference", actor_id=user.id, patient_id=patient.id
    )
    return consent_out(db.get(SummaryProcessingConsent, patient.id))


@router.post("/clinical/summary-assistance")
def generate(
    payload: SummaryInput,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(payload.patient_id)
    authorize_patient(db, user, target, request, any_resource=True)
    if settings.SUMMARY_PROVIDER == "http":
        # Serialize opt-out with processing. Provider changes invalidate old consent.
        locked = db.execute(
            update(SummaryProcessingConsent)
            .where(
                SummaryProcessingConsent.patient_id == target,
                SummaryProcessingConsent.enabled.is_(True),
                SummaryProcessingConsent.provider_reference == settings.SUMMARY_PROVIDER_REFERENCE,
            )
            .values(version=SummaryProcessingConsent.version)
            .execution_options(synchronize_session=False)
        )
        if locked.rowcount != 1:
            db.rollback()
            raise HTTPException(403, "The patient has not enabled this named summary processor")
    source = summary(
        db,
        target,
        payload.offset,
        payload.limit,
        allowed_resources=allowed_clinical_resources(db, user, target),
    )
    # The aggregate has independently bounded categories; cap the transmitted page too.
    source_facts = source["facts"][:50]
    try:
        facts = select_sources(source_facts)
    except ProviderUnavailable:
        db.rollback()
        raise HTTPException(
            502,
            "Summary processor unavailable or returned unsupported evidence. No generated statements were accepted.",
        ) from None
    audit_service.log_event(
        db,
        "REQUEST_SOURCE_SELECTION",
        "clinical_summary",
        actor_id=user.id,
        patient_id=target,
        details="provider=" + settings.SUMMARY_PROVIDER_REFERENCE,
    )
    return dict(
        mode="provider_selected_source_extracts"
        if settings.SUMMARY_PROVIDER == "http"
        else "local_source_extracts",
        provider_reference=settings.SUMMARY_PROVIDER_REFERENCE,
        facts=facts,
        interpretations=[],
        has_more=source["has_more"] or len(source["facts"]) > 50,
        limitations="Exact authorized source extracts only. Selection is not a clinical conclusion or verification. Missing information and source conflicts require clinician review.",
    )
