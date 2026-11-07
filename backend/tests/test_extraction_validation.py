import pytest
from app.services.extraction_validation import ValidationDataset, evaluate


def dataset(**changes):
    result = dict(
        mode="synthetic_only",
        reference="synthetic-validation-fixture",
        cases=[
            dict(
                case_id="synthetic-case-1",
                language="en",
                text="Medicine: SYNTHETIC-A | Dose: 1 unit",
                expected=[dict(name="SYNTHETIC-A", dose="1 unit")],
            )
        ],
    )
    result.update(changes)
    return ValidationDataset.model_validate(result)


def test_exact_field_metrics_do_not_claim_clinical_validation():
    result = evaluate(dataset())
    assert result["field_precision"] == result["field_recall"] == 1
    assert result["exact_cases"] == 1 and result["invalid_source_spans"] == 0
    assert not result["clinical_validation_complete"] and not result["production_approved"]
    assert "SYNTHETIC-A" not in str(result)


def test_wrong_or_falsely_filled_fields_are_measured_as_errors():
    data = dataset()
    data.cases[0].expected[0].dose = None
    result = evaluate(data)
    assert result["false_positive"] == result["false_filled_missing"] == 1
    assert result["exact_cases"] == 0 and result["field_precision"] == 0.5


def test_missing_expected_fields_reduce_recall_and_empty_denominators_stay_missing():
    data = dataset()
    data.cases[0].text = "No supported labelled medication assertions."
    result = evaluate(data)
    assert result["field_precision"] is None and result["field_recall"] == 0
    assert result["false_negative"] == 2


def test_approved_cases_need_opaque_ids_and_independent_annotation_reference():
    with pytest.raises(ValueError):
        evaluate(dataset(mode="approved_deidentified"))
    data = dataset(
        mode="approved_deidentified",
        approval_reference="approved-study-reference",
        independent_annotation_reference="independent-review-reference",
    )
    data.cases[0].case_id = "a" * 64
    assert evaluate(data)["mode"] == "approved_deidentified"
    with pytest.raises(ValueError):
        dataset(cases=[dict(case_id="Patient Jane Doe", language="en", text="", expected=[])])


def test_duplicate_cases_and_unknown_annotation_fields_are_rejected(tmp_path):
    data = dataset().model_dump()
    data["cases"] *= 2
    with pytest.raises(ValueError):
        ValidationDataset.model_validate(data)
    data = dataset().model_dump()
    data["cases"][0]["expected"][0]["invented_field"] = "SYNTHETIC_PRIVATE_VALUE"
    with pytest.raises(ValueError) as error:
        ValidationDataset.model_validate(data)
    assert "SYNTHETIC_PRIVATE_VALUE" not in str(error.value)
    import json
    import subprocess
    import sys
    from pathlib import Path

    private = tmp_path / "invalid-cases.json"
    private.write_text(json.dumps(data), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parents[2] / "scripts/evaluate_extraction.py"),
            "--dataset",
            str(private),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0 and "SYNTHETIC_PRIVATE_VALUE" not in result.stdout + result.stderr
    assert "contents were not printed" in result.stderr
