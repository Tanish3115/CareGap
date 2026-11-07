"""Evaluate explicit-label extraction from reviewed offline cases; no patient DB access."""

import argparse
import json
import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "backend"))
from app.services.extraction_validation import ValidationDataset, evaluate


def fixture():
    cases = []
    for language in ["en", "hi", "kn", "te", "ta", "ml"]:
        name = (
            "SYNTHETIC-"
            + {"en": "A", "hi": "हिंदी", "kn": "ಕನ್ನಡ", "te": "తెలుగు", "ta": "தமிழ்", "ml": "മലയാളം"}[language]
        )
        cases.append(
            dict(
                case_id="synthetic-labelled-" + language,
                language=language,
                text=f"Medicine: {name} | Dose: 1 test unit",
                expected=[dict(name=name, dose="1 test unit")],
            )
        )
        cases.append(
            dict(
                case_id="synthetic-unlabelled-" + language,
                language=language,
                text="Unclear source. No medication assertions.",
                expected=[],
            )
        )
    cases.append(
        dict(
            case_id="synthetic-unknown-dose",
            language="en",
            text="Medicine: SYNTHETIC-A\nDose: unclear",
            expected=[dict(name="SYNTHETIC-A")],
        )
    )
    return ValidationDataset(
        mode="synthetic_only", reference="synthetic-extraction-engine-fixture-v1", cases=cases
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        if args.dataset and args.dataset.stat().st_size > 20 * 1024 * 1024:
            raise ValueError("Dataset exceeds the offline evaluation limit")
        dataset = (
            ValidationDataset.model_validate_json(args.dataset.read_bytes()) if args.dataset else fixture()
        )
        report = evaluate(dataset)
    except (OSError, ValueError, TypeError):
        raise SystemExit(
            "Dataset validation failed. Review the private input locally; its contents were not printed."
        ) from None
    raw = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(args.output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as target:
            target.write(raw)
        print(
            json.dumps(
                dict(
                    mode=report["mode"],
                    cases=report["cases"],
                    exact_cases=report["exact_cases"],
                    artifact=str(args.output),
                )
            )
        )
    else:
        print(raw)


if __name__ == "__main__":
    main()
