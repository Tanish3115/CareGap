from datetime import datetime
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from app.schemas.terminology import TerminologyCoding

FIELD_NAMES = ("name", "strength", "dose", "route", "frequency", "duration", "instructions")
CORE_FIELDS = ("name", "strength", "dose", "route", "frequency", "duration")
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EvidenceValue(StrictInput):
    value: str = Field(min_length=1, max_length=500)
    start: int = Field(ge=0, le=100000)
    end: int = Field(ge=1, le=100000)
    checked: bool = False
    uncertain: bool = True


class PrescriptionItem(StrictInput):
    source_start: int = Field(ge=0, le=100000)
    source_end: int = Field(ge=1, le=100000)
    name: EvidenceValue | None = None
    strength: EvidenceValue | None = None
    dose: EvidenceValue | None = None
    route: EvidenceValue | None = None
    frequency: EvidenceValue | None = None
    duration: EvidenceValue | None = None
    instructions: EvidenceValue | None = None
    coding: TerminologyCoding | None = None


class PrescriptionContext(StrictInput):
    doctor_name: EvidenceValue | None = None
    consultation_date: EvidenceValue | None = None
    clinic: EvidenceValue | None = None
    follow_up_instructions: list[EvidenceValue] = Field(default_factory=list, max_length=20)
    test_recommendations: list[EvidenceValue] = Field(default_factory=list, max_length=20)


class GeneratePrescription(StrictInput):
    expected_version: int = Field(ge=0)
    source_review_version: int = Field(ge=1)


class SavePrescription(GeneratePrescription):
    items: list[PrescriptionItem] = Field(max_length=50)
    context: PrescriptionContext = Field(default_factory=PrescriptionContext)
    reason: Reason
    source_checked: Literal[True]
    confirm: bool = False
    missing_fields_acknowledged: bool = False


class PrescriptionOut(BaseModel):
    id: str
    document_id: str
    patient_id: str
    version: int
    source_review_version: int
    source_text: str
    source_sha256: str
    source_stale: bool
    state: Literal["draft", "clinician_confirmed"]
    items: list[PrescriptionItem]
    context: PrescriptionContext = Field(default_factory=PrescriptionContext)
    missing_fields: list[list[str]]
    extractor_version: str
    author_name: str
    author_role: str
    reason: str
    created_at: datetime
    can_edit: bool
    can_confirm: bool


class MedicationEntryOut(BaseModel):
    id: str
    patient_id: str
    document_id: str
    prescription_version: int
    record_kind: Literal["documented_prescription"] = "documented_prescription"
    name: str
    strength: str | None
    dose: str | None
    route: str | None
    frequency: str | None
    duration: str | None
    instructions: str | None
    needs_clarification: bool
    missing_fields: list[str]
    source_stale: bool
    draft_pending: bool
    evidence: PrescriptionItem
    confirmed_by_name: str
    created_at: datetime
    coding: TerminologyCoding | None = None
