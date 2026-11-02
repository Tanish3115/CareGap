from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator
from app.core.time import utc_now

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class ReportFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Text
    dose: Text | None = None
    frequency: Text | None = None
    use_status: Literal["taking", "not_taking", "unknown"]
    reported_on: date
    notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)] | None = (
        None
    )
    source_entry_id: UUID | None = None
    reason: Reason

    @field_validator("reported_on")
    @classmethod
    def no_future_report(cls, value):
        if value > utc_now().date():
            raise ValueError("Report date cannot be in the future")
        return value


class ReportCreate(ReportFields):
    patient_id: UUID


class ReportCorrect(ReportFields):
    expected_version: int = Field(ge=1)


class ReconcileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_report_version: int = Field(ge=1)
    expected_review_version: int = Field(ge=0)
    expected_source_review_version: int | None = Field(default=None, ge=1)
    expected_prescription_version: int | None = Field(default=None, ge=1)
    assessment: Literal["account_reviewed", "discrepancy", "needs_clarification"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=2000)]
    comparison_checked: Literal[True]


class ReviewOut(BaseModel):
    id: str
    version: int
    report_version: int
    assessment: str
    note: str
    source_snapshot: dict | None
    recorded_by_name: str
    created_at: datetime


class ReportOut(BaseModel):
    id: str
    patient_id: str
    version: int
    review_version: int
    name: str
    dose: str | None
    frequency: str | None
    use_status: str
    reported_on: date
    notes: str | None
    source_entry_id: str | None
    source: dict | None
    provenance: Literal["patient_reported"] = "patient_reported"
    reason: str
    recorded_by_name: str
    created_at: datetime
    latest_review: ReviewOut | None
    review_stale: bool
