import json
from pathlib import Path
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.api.clinical import authorize_patient
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.clinical_summary import summary
from app.services.medication_review import review_medications
from app.services.synthetic_risk import FEATURES, predict
from app.services.authorization import allowed_clinical_resources

router = APIRouter(tags=["Source-linked overview and review support"])


@router.get("/clinical/overview")
def overview(
    patient_id: UUID,
    request: Request,
    offset: int = 0,
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not 0 <= offset or not 1 <= limit <= 100:
        raise HTTPException(422, "Invalid overview page")
    target = str(patient_id)
    authorize_patient(db, user, target, request, any_resource=True)
    result = summary(
        db, target, offset, limit, allowed_resources=allowed_clinical_resources(db, user, target)
    )
    audit_service.log_event(
        db, "VIEW_SOURCE_OVERVIEW", "clinical_summary", actor_id=user.id, patient_id=target
    )
    return result


@router.get("/clinical/medication-review")
def medication_review(
    patient_id: UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    target = str(patient_id)
    authorize_patient(db, user, target, request, resource="medications")
    result = review_medications(
        db, target, include_allergies="allergies" in allowed_clinical_resources(db, user, target)
    )
    audit_service.log_event(
        db, "VIEW_MEDICATION_INDICATORS", "medication_review", actor_id=user.id, patient_id=target
    )
    return result


def artifact():
    path = Path(__file__).resolve().parents[1] / "data/synthetic_risk.json"
    if not path.exists():
        raise HTTPException(
            503, "Run scripts/evaluate_synthetic.py to generate the synthetic evaluation artifact"
        )
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/research/synthetic-risk")
def risk_evaluation(user: User = Depends(get_current_user)):
    return artifact()


@router.get("/research/model-comparison")
def model_comparison(user: User = Depends(get_current_user)):
    path = Path(__file__).resolve().parents[1] / "data/synthetic_models.json"
    if not path.exists():
        raise HTTPException(503, "Run research/compare_models.py in the optional research environment")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get("/research/intervention-study")
def synthetic_intervention_study(user: User = Depends(get_current_user)):
    path = Path(__file__).resolve().parents[1] / "data/synthetic_interventions.json"
    if not path.exists():
        raise HTTPException(503, "Synthetic intervention artifact is unavailable")
    result = json.loads(path.read_text(encoding="utf-8"))
    if (
        result.get("mode") != "synthetic_only"
        or result.get("clinical_causal_validation") is not False
        or result.get("automatic_interventions") is not False
    ):
        raise HTTPException(503, "Only the synthetic intervention artifact can be served here")
    return result


class SyntheticCase(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prior_missed: int = Field(ge=0, le=5)
    prior_incomplete_referrals: int = Field(ge=0, le=5)
    days_since_visit: int = Field(ge=1, le=365)
    lead_days: int = Field(ge=1, le=90)
    barrier_count: int = Field(ge=0, le=5)


@router.post("/research/synthetic-risk")
def synthetic_case(payload: SyntheticCase, user: User = Depends(get_current_user)):
    model = artifact()
    probability, contributions = predict(model["weights"], [getattr(payload, key) for key in FEATURES])
    return dict(
        mode="synthetic_only",
        synthetic_probability=probability,
        intercept=model["weights"][0],
        signed_log_odds_contributions=contributions,
        limitations=model["limitations"],
    )
