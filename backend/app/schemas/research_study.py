"""Offline research envelopes. No clinical identifiers or free-text patient fields."""

from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResearchEnvelope(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="after")
    @classmethod
    def utc_timestamps(cls, value):
        if isinstance(value, datetime):
            if value.tzinfo is None:
                raise ValueError("Explicit timezone required")
            return value.astimezone(timezone.utc)
        return value


class StudyProtocol(ResearchEnvelope):
    study_id: str = Field(pattern=r"^[A-Za-z0-9._-]{3,80}$")
    mode: Literal["synthetic", "approved_deidentified"]
    allocation: Literal["randomized", "observational"]
    registered_at: datetime
    analysis_cutoff: datetime
    outcome_window_days: int = Field(ge=1, le=365)
    assignment_probability: float = Field(ge=0.1, le=0.9)
    approval_reference: str = Field(min_length=5, max_length=150, pattern=r"^[A-Za-z0-9._:/-]+$")
    research_use_authorized: Literal[True]
    outcome_definition: Literal["documented_care_completion_within_window"]


class StudyParticipant(ResearchEnvelope):
    unit_id: str = Field(pattern=r"^(synthetic-unit-[0-9]{1,8}|[a-f0-9]{64})$")
    assigned_at: datetime
    baseline_measured_at: datetime
    assigned_arm: Literal[0, 1]
    received_intervention: Literal[0, 1] | None
    assignment_probability: float = Field(ge=0.1, le=0.9)
    outcome: Literal[0, 1] | None
    outcome_recorded_at: datetime | None
    observed_through: datetime | None
    prior_missed: int = Field(ge=0, le=50)
    barrier_count: int = Field(ge=0, le=10)

    @model_validator(mode="after")
    def validate_timing(self):
        if self.baseline_measured_at >= self.assigned_at:
            raise ValueError("Post-assignment baseline information is prohibited")
        if (self.outcome is None) != (self.outcome_recorded_at is None):
            raise ValueError("Outcome values require their observation timestamp")
        if self.outcome_recorded_at and self.outcome_recorded_at < self.assigned_at:
            raise ValueError("Pre-assignment outcomes are prohibited")
        return self
