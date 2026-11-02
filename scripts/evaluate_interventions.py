"""Offline evaluation; default generates synthetic units without opening the application DB."""

import argparse
import json
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.schemas.research_study import StudyParticipant, StudyProtocol
from app.services.intervention_study import evaluate_study


def synthetic_study(seed=360):
    rng = random.Random(seed)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    protocol = StudyProtocol(
        study_id="synthetic-intervention-v1",
        mode="synthetic",
        allocation="randomized",
        registered_at=start - timedelta(days=1),
        analysis_cutoff=start + timedelta(days=120),
        outcome_window_days=30,
        assignment_probability=0.5,
        approval_reference="SYNTHETIC-SOFTWARE-FIXTURE",
        research_use_authorized=True,
        outcome_definition="documented_care_completion_within_window",
    )
    rows = []
    for index in range(2000):
        assigned = start + timedelta(days=index // 40)
        arm = int(rng.random() < 0.5)
        barriers = rng.randrange(4)
        prior = rng.randrange(4)
        probability = 0.30 + 0.12 * arm - 0.03 * barriers - 0.02 * prior
        outcome = int(rng.random() < probability)
        rows.append(
            StudyParticipant(
                unit_id=f"synthetic-unit-{index}",
                assigned_at=assigned,
                baseline_measured_at=assigned - timedelta(days=1),
                assigned_arm=arm,
                received_intervention=arm,
                assignment_probability=0.5,
                outcome=outcome,
                outcome_recorded_at=assigned + timedelta(days=30),
                observed_through=assigned + timedelta(days=30),
                prior_missed=prior,
                barrier_count=barriers,
            )
        )
    return protocol, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if bool(args.protocol) != bool(args.dataset):
        parser.error("Provide both protocol and dataset, or neither for synthetic mode")
    if args.protocol:
        if not args.output:
            parser.error("External research inputs require a new private output path")
        if args.dataset.stat().st_size > 20 * 1024 * 1024:
            parser.error("Dataset exceeds the bounded research input size")
        protocol = StudyProtocol.model_validate_json(args.protocol.read_bytes())
        rows = [
            StudyParticipant.model_validate(row)
            for row in json.loads(args.dataset.read_text(encoding="utf-8"))
        ]
    else:
        protocol, rows = synthetic_study()
    result = evaluate_study(protocol, rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2)
            stream.write("\n")
        print(json.dumps(dict(mode=result["mode"], output=str(args.output), units=len(rows))))
    else:
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError):
        raise SystemExit("Research input/output validation failed; no participant contents printed") from None
