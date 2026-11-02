from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator
from app.core.input_text import safe_text
from app.core.time import utc_now

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Note = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=500)]
Kind = Literal[
    "diagnosis",
    "allergy",
    "lab",
    "appointment",
    "referral",
    "test",
    "medication_order",
    "dispensing",
    "confirmed_use",
    "intervention",
]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")
    _safe_text = field_validator("*", mode="after")(safe_text)


class Diagnosis(Strict):
    kind: Literal["diagnosis"]
    condition: Text
    status: Literal["active", "resolved", "unknown"] = "unknown"
    notes: Note | None = None


class Allergy(Strict):
    kind: Literal["allergy"]
    substance: Text
    reaction: Text | None = None
    status: Literal["active", "inactive", "unknown"] = "unknown"
    notes: Note | None = None


class Lab(Strict):
    kind: Literal["lab"]
    test_name: Text
    value: Text | None = None
    unit: Text | None = None
    reference_range: Text | None = None
    notes: Note | None = None


class CareEvent(Strict):
    kind: Literal["appointment", "referral", "test"]
    due_on: date
    status: Literal["pending", "completed", "missed", "cancelled", "unknown"] = "pending"
    outcome: Note | None = None
    barriers: list[
        Literal["transport", "cost", "language", "instructions", "scheduling", "other", "unknown"]
    ] = Field(default_factory=list, max_length=7)
    notes: Note | None = None
    reschedule_requested_for: date | None = None
    reschedule_reason: Text | None = None
    reschedule_decision: Literal["requested", "approved", "declined"] | None = None
    reschedule_review_note: Note | None = None

    @model_validator(mode="after")
    def outcome_required(self):
        if self.reschedule_decision:
            if not self.reschedule_requested_for or not self.reschedule_reason:
                raise ValueError("Rescheduling requires a requested date and reason")
            if self.reschedule_decision in ("approved", "declined") and not self.reschedule_review_note:
                raise ValueError("Rescheduling decisions need a clinician review note")
            if self.reschedule_decision == "approved" and self.due_on != self.reschedule_requested_for:
                raise ValueError("Approved rescheduling must use the reviewed requested date")
        elif any((self.reschedule_requested_for, self.reschedule_reason, self.reschedule_review_note)):
            raise ValueError("Select a rescheduling request/decision state")
        if self.status in ("completed", "missed", "cancelled") and not self.outcome:
            raise ValueError("A terminal care status needs an attributed outcome report")
        if self.status in ("completed", "missed") and self.due_on > utc_now().date():
            raise ValueError("Future care cannot already be marked completed or missed")
        self.barriers = sorted(set(self.barriers))
        return self


class MedicationEvent(Strict):
    kind: Literal["medication_order", "dispensing", "confirmed_use"]
    name: Text
    strength: Text | None = None
    dose: Text | None = None
    frequency: Text | None = None
    route: Text | None = None
    instructions: Note | None = None
    start_on: date | None = None
    end_on: date | None = None
    status: Literal["recorded", "cancelled", "taking", "not_taking", "unknown"] = "unknown"
    terminology_code: Text | None = None
    terminology_system: Text | None = None
    terminology_evidence: Text | None = None
    notes: Note | None = None

    @model_validator(mode="after")
    def consistent_fields(self):
        if self.start_on and self.end_on and self.end_on < self.start_on:
            raise ValueError("Medication end precedes start")
        if any((self.terminology_code, self.terminology_system, self.terminology_evidence)) and not all(
            (self.terminology_code, self.terminology_system, self.terminology_evidence)
        ):
            raise ValueError("Terminology mapping requires code, system and evidence; no inferred mappings")
        allowed = (
            ("taking", "not_taking", "unknown")
            if self.kind == "confirmed_use"
            else ("recorded", "cancelled", "unknown")
        )
        if self.status not in allowed:
            raise ValueError("Status does not apply to this medication event")
        return self


class Intervention(Strict):
    kind: Literal["intervention"]
    target_id: UUID
    target_version: int = Field(ge=1)
    action: Literal[
        "rescheduling",
        "reminder",
        "staff_outreach",
        "transport_referral",
        "financial_referral",
        "instruction_clarification",
    ]
    status: Literal["proposed", "assigned", "completed", "declined", "cancelled"] = "proposed"
    assigned_staff: Text | None = None
    outcome: Note | None = None
    notes: Note | None = None
    experiment_reference: Text | None = None

    @model_validator(mode="after")
    def terminal_outcome(self):
        if self.status in ("completed", "declined", "cancelled") and not self.outcome:
            raise ValueError("Record the intervention outcome, including explicit unknown outcomes")
        if self.status == "assigned" and not self.assigned_staff:
            raise ValueError("Assigned intervention needs a named staff reviewer")
        return self


Data = Annotated[
    Diagnosis | Allergy | Lab | CareEvent | MedicationEvent | Intervention, Field(discriminator="kind")
]


class RecordFields(Strict):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)]
    occurred_on: date
    data: Data
    reason: Reason
    source_document_ids: list[UUID] = Field(default_factory=list, max_length=50)
    source_checked: Literal[True]

    @model_validator(mode="after")
    def not_future_account(self):
        if self.occurred_on > utc_now().date():
            raise ValueError("Record date cannot be in the future; use the care due date for future plans")
        return self


class RecordCreate(RecordFields):
    patient_id: UUID


class RecordCorrect(RecordFields):
    expected_version: int = Field(ge=1)


class SourceOut(BaseModel):
    id: str
    title: str
    file_name: str


class RecordOut(BaseModel):
    id: str
    patient_id: str
    kind: Kind
    version: int
    title: str
    occurred_on: date
    data: Data
    reason: str
    provenance: str
    recorded_by_name: str
    recorded_at: datetime
    sources: list[SourceOut]
    linked_record_stale: bool = False
    external_source: dict | None = None
