from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import subprocess
import sys
import pytest
from app.schemas.research_study import StudyParticipant, StudyProtocol
from app.services.intervention_study import evaluate_study


def fixture():
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    protocol = StudyProtocol(
        study_id="synthetic-study-test",
        mode="synthetic",
        allocation="randomized",
        registered_at=start - timedelta(days=1),
        analysis_cutoff=start + timedelta(days=60),
        outcome_window_days=30,
        assignment_probability=0.5,
        approval_reference="SYNTHETIC-ONLY",
        research_use_authorized=True,
        outcome_definition="documented_care_completion_within_window",
    )
    rows = [
        StudyParticipant(
            unit_id=f"synthetic-unit-{index}",
            assigned_at=start,
            baseline_measured_at=start - timedelta(days=1),
            assigned_arm=index % 2,
            received_intervention=0,
            assignment_probability=0.5,
            outcome=int(index % 4 in (0, 1, 3)),
            outcome_recorded_at=start + timedelta(days=30),
            observed_through=start + timedelta(days=30),
            prior_missed=1,
            barrier_count=2,
        )
        for index in range(80)
    ]
    return protocol, rows


def test_registered_assigned_arm_analysis_reports_uncertainty_without_clinical_claims():
    protocol, rows = fixture()
    result = evaluate_study(protocol, rows)
    assert result == evaluate_study(protocol, list(reversed(rows)))
    assert result["registered_randomized_complete_outcome_difference"] == 0.5
    assert (
        result["assigned_arm_counts"][1]["not_received"] == 40
    )  # Receiving treatment never changes assignment.
    assert result["normal_approximation_95_interval"] is None  # One arm has no negative outcomes.
    assert result["missing_outcome_difference_bounds"] == [0.5, 0.5]
    assert not result["clinical_causal_validation"] and not result["automatic_interventions"]
    assert "unit_id" not in str(result)


def test_missing_outcomes_are_bounded_not_imputed_as_failed_care():
    protocol, rows = fixture()
    rows[1] = rows[1].model_copy(update=dict(outcome=None, outcome_recorded_at=None, observed_through=None))
    result = evaluate_study(protocol, rows)
    assert result["registered_randomized_complete_outcome_difference"] is None
    assert result["assigned_arm_counts"][1]["missing_or_immature"] == 1
    assert result["assigned_arm_counts"][1]["not_completed"] == 0
    assert result["missing_outcome_difference_bounds"][0] < result["missing_outcome_difference_bounds"][1]


def test_complete_synthetic_groups_get_a_labelled_interval_when_counts_support_it():
    protocol, rows = fixture()
    for index in range(1, 40, 4):
        rows[index] = rows[index].model_copy(update=dict(outcome=0))
    result = evaluate_study(protocol, rows)
    estimate = result["registered_randomized_complete_outcome_difference"]
    assert estimate == 0.25 and result["standard_error"] > 0
    assert (
        result["normal_approximation_95_interval"][0]
        < estimate
        < result["normal_approximation_95_interval"][1]
    )


def test_observational_counts_never_become_a_causal_effect_estimate():
    protocol, rows = fixture()
    protocol.allocation = "observational"
    result = evaluate_study(protocol, rows)
    assert result["observed_case_difference"] == 0.5
    assert result["registered_randomized_complete_outcome_difference"] is None
    assert result["normal_approximation_95_interval"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "repeated",
        "post_baseline",
        "future",
        "early_negative",
        "unobserved_negative",
        "registration",
        "probability",
        "one_arm",
        "identifier",
        "extra_phi",
    ],
)
def test_research_envelope_rejects_leakage_invalid_outcomes_and_personal_identifiers(fault):
    protocol, rows = fixture()
    row = rows[0].model_dump()
    if fault == "repeated":
        rows.append(rows[0])
    elif fault == "post_baseline":
        row["baseline_measured_at"] = row["assigned_at"]
    elif fault == "future":
        row["outcome_recorded_at"] = protocol.analysis_cutoff + timedelta(days=1)
    elif fault == "early_negative":
        row.update(outcome=0, outcome_recorded_at=row["assigned_at"] + timedelta(days=1))
    elif fault == "unobserved_negative":
        row.update(outcome=0, observed_through=None)
    elif fault == "registration":
        protocol.registered_at = row["assigned_at"]
    elif fault == "probability":
        row["assignment_probability"] = 0.3
    elif fault == "one_arm":
        rows = [item for item in rows if item.assigned_arm == 0]
    elif fault == "identifier":
        row["unit_id"] = "real-patient@example.com"
    elif fault == "extra_phi":
        row["patient_name"] = "forbidden even in tests"
    with pytest.raises(ValueError):
        if fault not in ("repeated", "one_arm"):
            rows[0] = StudyParticipant.model_validate(row)
        evaluate_study(protocol, rows)


def test_synthetic_research_artifact_is_authenticated_and_reproduces_without_a_database(
    client, patient_token
):
    from tests.test_hardening import headers

    url = "/api/v1/research/intervention-study"
    assert client.get(url).status_code == 401
    result = client.get(url, headers=headers(patient_token))
    assert result.status_code == 200
    assert result.json()["mode"] == "synthetic_only" and result.json()["individual_treatment_effects"] is None
    root = Path(__file__).resolve().parents[2]
    process = subprocess.run(
        [sys.executable, str(root / "scripts/evaluate_interventions.py")],
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(process.stdout) == result.json()
