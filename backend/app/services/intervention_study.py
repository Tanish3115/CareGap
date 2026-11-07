"""Offline registered-study diagnostics. Does not allocate or intervene on patients."""

import hashlib
import json
import math
from datetime import timedelta
from app.schemas.research_study import StudyParticipant, StudyProtocol


def checksum(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def evaluate_study(protocol: StudyProtocol, participants: list[StudyParticipant]):
    if not 2 <= len(participants) <= 20000:
        raise ValueError("Study needs 2–20000 distinct assignment units")
    if len({row.unit_id for row in participants}) != len(participants):
        raise ValueError("Repeated assignment units require a different prespecified design")
    arms = {
        arm: dict(
            assigned=0, completed=0, not_completed=0, missing_or_immature=0, not_received=0, receipt_unknown=0
        )
        for arm in (0, 1)
    }
    baseline = {arm: {"prior_missed": [], "barrier_count": []} for arm in (0, 1)}
    for row in participants:
        if protocol.mode == "synthetic" and not row.unit_id.startswith("synthetic-unit-"):
            raise ValueError("Synthetic mode rejects non-synthetic identifiers")
        if protocol.mode == "approved_deidentified" and row.unit_id.startswith("synthetic-unit-"):
            raise ValueError("Approved-data mode requires pseudonymous hashed units")
        if row.assigned_at <= protocol.registered_at or row.assigned_at > protocol.analysis_cutoff:
            raise ValueError("Register the design before assignment and respect the analysis cutoff")
        if (
            protocol.allocation == "randomized"
            and row.assignment_probability != protocol.assignment_probability
        ):
            raise ValueError("Unsupported varying randomization probability")
        end = row.assigned_at + timedelta(days=protocol.outcome_window_days)
        if row.outcome_recorded_at and row.outcome_recorded_at > protocol.analysis_cutoff:
            raise ValueError("Future outcome leakage")
        if row.observed_through and (
            row.observed_through < row.assigned_at or row.observed_through > protocol.analysis_cutoff
        ):
            raise ValueError("Invalid follow-up observation interval")
        if row.outcome == 1 and row.outcome_recorded_at > end:
            raise ValueError("Completion outside the registered window")
        if row.outcome == 0 and (not row.observed_through or row.observed_through < end):
            raise ValueError("Unobserved follow-up must not be coded as failed care")
        if row.outcome == 0 and row.outcome_recorded_at < end:
            raise ValueError("Negative outcomes require the complete registered window")
        arm = arms[row.assigned_arm]
        arm["assigned"] += 1
        if row.received_intervention is None:
            arm["receipt_unknown"] += 1
        elif row.received_intervention == 0:
            arm["not_received"] += 1
        for field in baseline[row.assigned_arm]:
            baseline[row.assigned_arm][field].append(getattr(row, field))
        mature = (
            end <= protocol.analysis_cutoff
            and row.outcome is not None
            and row.observed_through
            and row.observed_through >= end
        )
        arm["completed" if row.outcome == 1 else "not_completed"] += 1 if mature else 0
        arm["missing_or_immature"] += 0 if mature else 1
    if any(arm["assigned"] == 0 for arm in arms.values()):
        raise ValueError("Both comparison arms are required")
    for arm in arms.values():
        observed = arm["completed"] + arm["not_completed"]
        arm["observed_completion_rate"] = arm["completed"] / observed if observed else None
        arm["all_assigned_rate_bounds"] = [
            arm["completed"] / arm["assigned"],
            (arm["completed"] + arm["missing_or_immature"]) / arm["assigned"],
        ]
    control, treatment = arms[0], arms[1]
    complete = all(arm["missing_or_immature"] == 0 for arm in arms.values())
    difference = (
        treatment["observed_completion_rate"] - control["observed_completion_rate"]
        if all(arm["observed_completion_rate"] is not None for arm in arms.values())
        else None
    )
    randomized_estimate = difference if complete and protocol.allocation == "randomized" else None
    standard_error = None
    interval = None
    if randomized_estimate is not None and all(
        arm["assigned"] >= 20 and arm["completed"] >= 5 and arm["not_completed"] >= 5 for arm in arms.values()
    ):
        variance = sum(
            arm["observed_completion_rate"] * (1 - arm["observed_completion_rate"]) / (arm["assigned"] - 1)
            for arm in arms.values()
        )
        standard_error = math.sqrt(variance)
        interval = [
            max(-1, randomized_estimate - 1.96 * standard_error),
            min(1, randomized_estimate + 1.96 * standard_error),
        ]
    balance = {}
    for field in ("prior_missed", "barrier_count"):
        means = [sum(baseline[arm][field]) / len(baseline[arm][field]) for arm in (0, 1)]
        balance[field] = dict(
            control_mean=means[0],
            assigned_intervention_mean=means[1],
            unadjusted_mean_difference=means[1] - means[0],
        )
    return dict(
        mode="synthetic_only" if protocol.mode == "synthetic" else "approved_deidentified_research_only",
        study_id=protocol.study_id,
        protocol_sha256=checksum(protocol.model_dump(mode="json")),
        dataset_sha256=checksum(
            [row.model_dump(mode="json") for row in sorted(participants, key=lambda row: row.unit_id)]
        ),
        assigned_arm_counts=arms,
        baseline_balance=balance,
        analyzed_by="assigned_arm_not_received_treatment",
        observed_case_difference=difference,
        registered_randomized_complete_outcome_difference=randomized_estimate,
        standard_error=standard_error,
        normal_approximation_95_interval=interval,
        missing_outcome_difference_bounds=[
            treatment["all_assigned_rate_bounds"][0] - control["all_assigned_rate_bounds"][1],
            treatment["all_assigned_rate_bounds"][1] - control["all_assigned_rate_bounds"][0],
        ],
        clinical_causal_validation=False,
        individual_treatment_effects=None,
        automatic_interventions=False,
        limitations=[
            "Research software output, not clinical effectiveness or an individualized treatment recommendation.",
            "Randomization and approval references are operator assertions requiring independent verification.",
            "Missing/immature outcomes are not failures; no effect estimate is returned with missing outcomes or observational allocation.",
            "Worst/best binary-outcome bounds are sensitivity checks, not confidence intervals.",
            "The normal approximation interval is only provided with at least 20 assigned and five observed outcomes of each value in each arm.",
            "Observational comparisons remain unadjusted associations; confounding, selection bias, interference and measurement error require separate study review.",
        ],
    )
