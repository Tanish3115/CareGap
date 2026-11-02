"""Offline exact-field evaluation. Does not import or query the patient database."""

import hashlib
import json
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.schemas.prescription import FIELD_NAMES
from app.services.prescription_extraction import extract_explicit_lines


class ExpectedMedication(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    name: str | None = Field(default=None, max_length=500)
    strength: str | None = Field(default=None, max_length=500)
    dose: str | None = Field(default=None, max_length=500)
    route: str | None = Field(default=None, max_length=500)
    frequency: str | None = Field(default=None, max_length=500)
    duration: str | None = Field(default=None, max_length=500)
    instructions: str | None = Field(default=None, max_length=500)


class ExtractionCase(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    case_id: str = Field(pattern=r"^(?:synthetic-[A-Za-z0-9_-]{1,80}|[0-9a-f]{64})$")
    language: Literal["en", "hi", "kn", "te", "ta", "ml"]
    text: str = Field(max_length=100000)
    expected: list[ExpectedMedication] = Field(max_length=50)


class ValidationDataset(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    mode: Literal["synthetic_only", "approved_deidentified"]
    reference: str = Field(min_length=5, max_length=200)
    approval_reference: str | None = Field(default=None, max_length=200)
    independent_annotation_reference: str | None = Field(default=None, max_length=200)
    cases: list[ExtractionCase] = Field(min_length=1, max_length=10000)

    @field_validator("cases")
    @classmethod
    def unique_cases(cls, value):
        if len({row.case_id for row in value}) != len(value):
            raise ValueError("Repeated case identifiers would inflate evaluation")
        return value


def evaluate(dataset: ValidationDataset):
    synthetic = dataset.mode == "synthetic_only"
    if not synthetic and (not dataset.approval_reference or not dataset.independent_annotation_reference):
        raise ValueError("Approved data requires approval and independent annotation references")
    if any(row.case_id.startswith("synthetic-") != synthetic for row in dataset.cases):
        raise ValueError("Case identities must match the declared dataset mode")
    totals = dict(
        true_positive=0, false_positive=0, false_negative=0, false_filled_missing=0, invalid_source_spans=0
    )
    groups = {}
    exact_cases = 0
    case_checksums = []
    for case in dataset.cases:
        predicted = extract_explicit_lines(case.text)
        expected = case.expected
        observed = set()
        wanted = set()
        invalid = 0
        for index, item in enumerate(predicted):
            for field in FIELD_NAMES:
                source = getattr(item, field)
                if source is not None:
                    observed.add((index, field, source.value))
                    invalid += int(
                        case.text[source.start : source.end] != source.value
                        or source.checked
                        or not source.uncertain
                    )
        for index, item in enumerate(expected):
            for field in FIELD_NAMES:
                value = getattr(item, field)
                if value is not None:
                    wanted.add((index, field, value))
        counts = dict(
            true_positive=len(observed & wanted),
            false_positive=len(observed - wanted),
            false_negative=len(wanted - observed),
            false_filled_missing=sum(
                1
                for index, field, _ in observed
                if index >= len(expected) or getattr(expected[index], field) is None
            ),
            invalid_source_spans=invalid,
        )
        exact = observed == wanted and len(predicted) == len(expected) and invalid == 0
        exact_cases += int(exact)
        group = groups.setdefault(case.language, dict(cases=0, exact_cases=0, **{key: 0 for key in totals}))
        group["cases"] += 1
        group["exact_cases"] += int(exact)
        for key, value in counts.items():
            totals[key] += value
            group[key] += value
        case_checksums.append(hashlib.sha256(case.text.encode()).hexdigest())
    tp, fp, fn = totals["true_positive"], totals["false_positive"], totals["false_negative"]
    return dict(
        schema_version="caregap-extraction-validation-v1",
        mode=dataset.mode,
        dataset_reference=dataset.reference,
        cases=len(dataset.cases),
        exact_cases=exact_cases,
        exact_case_rate=exact_cases / len(dataset.cases),
        field_precision=tp / (tp + fp) if tp + fp else None,
        field_recall=tp / (tp + fn) if tp + fn else None,
        **totals,
        language_groups=groups,
        source_manifest_sha256=hashlib.sha256("\n".join(case_checksums).encode()).hexdigest(),
        dataset_sha256=hashlib.sha256(
            json.dumps(dataset.model_dump(mode="json"), sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest(),
        clinical_validation_complete=False,
        production_approved=False,
        scope="Explicit-label text extraction only; OCR accuracy, handwriting, clinical correctness, patient outcomes and independent review are not established by this report.",
    )
