from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class DocumentReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=0)
    expected_attempt: int = Field(ge=1, le=3)
    reviewed_text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100000)]
    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
    source_checked: Literal[True]


class DocumentReviewOut(BaseModel):
    document_id: str
    version: int
    processing_job_id: str
    processing_attempt: int
    processor_version: str
    source_sha256: str
    source_text: str
    reviewed_text: str
    reviewer_id: str
    reviewer_name: str
    reviewer_kind: Literal["patient_reviewed", "clinician_reviewed"]
    reason: str
    created_at: datetime
