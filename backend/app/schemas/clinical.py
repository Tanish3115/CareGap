from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from app.core.time import utc_now

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
Provenance = Literal["patient_reported", "clinician_recorded"]
TaskStatus = Literal["pending", "completed", "cancelled"]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EncounterIn(StrictInput):
    occurred_on: date
    title: Title
    notes: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]
    source_document_ids: list[UUID] = Field(default_factory=list, max_length=50)

    @field_validator("occurred_on")
    @classmethod
    def past_or_today(cls, value):
        if value > utc_now().date():
            raise ValueError("Consultation date cannot be in the future")
        return value


class EncounterCreate(EncounterIn):
    patient_id: UUID


class EncounterCorrect(EncounterIn):
    expected_version: int = Field(ge=1)
    correction_reason: Reason


class SourceOut(BaseModel):
    id: str
    title: str
    file_name: str


class EncounterOut(BaseModel):
    id: str
    patient_id: str
    created_by: str
    version: int
    occurred_on: date
    title: str
    notes: str
    sources: list[SourceOut]
    recorded_by: str
    recorded_by_name: str
    provenance: Provenance
    correction_reason: str
    recorded_at: datetime
    created_at: datetime


class FollowUpIn(StrictInput):
    title: Title
    due_on: date
    status: TaskStatus = "pending"
    outcome: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None

    @model_validator(mode="after")
    def require_outcome(self):
        if self.status != "pending" and not self.outcome:
            raise ValueError("A completion report or cancellation reason is required")
        if self.status == "pending" and self.outcome:
            raise ValueError("Pending tasks cannot have a completion outcome")
        return self


class FollowUpCreate(FollowUpIn):
    encounter_id: UUID


class FollowUpCorrect(FollowUpIn):
    expected_version: int = Field(ge=1)
    correction_reason: Reason


class FollowUpOut(BaseModel):
    id: str
    patient_id: str
    encounter_id: str
    created_by: str
    version: int
    title: str
    due_on: date
    status: TaskStatus
    outcome: str | None
    overdue: bool
    recorded_by: str
    recorded_by_name: str
    provenance: Provenance
    correction_reason: str
    recorded_at: datetime
    created_at: datetime


class TimelineOut(BaseModel):
    id: str
    kind: Literal["document", "encounter"]
    event_date: date
    date_basis: Literal["clinical_date", "upload_date", "consultation_date"]
    title: str
    provenance: Literal["source_unverified", "patient_reported", "clinician_recorded"]
