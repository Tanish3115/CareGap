"""Reproducible synthetic-only logistic baseline. Never auto-scores patient records."""

import math
import random
from datetime import date, timedelta

FEATURES = ("prior_missed", "prior_incomplete_referrals", "days_since_visit", "lead_days", "barrier_count")
SCALES = (5, 5, 365, 90, 5)


def sigmoid(value):
    return 1 / (1 + math.exp(-max(-40, min(40, value))))


def examples(seed=360, count=1800):
    rng = random.Random(seed)
    rows = []
    for index in range(count):
        features = [
            rng.randint(0, 5),
            rng.randint(0, 5),
            rng.randint(1, 365),
            rng.randint(1, 90),
            rng.randint(0, 5),
        ]
        x = [value / scale for value, scale in zip(features, SCALES)]
        p = sigmoid(-3.8 + 2.0 * x[0] + 1.2 * x[1] + 0.8 * x[2] + 0.5 * x[3] + 1.5 * x[4])
        index_date = date(2020, 1, 1) + timedelta(days=index)
        rows.append(
            dict(
                patient_id=f"synthetic-{index}",
                index_date=index_date.isoformat(),
                feature_cutoff=(index_date - timedelta(days=1)).isoformat(),
                features=features,
                outcome=int(rng.random() < p),
                subgroup="synthetic_group_a" if index % 2 else "synthetic_group_b",
            )
        )
    return rows


def leakage_check(train, validation, test):
    if not train or not validation or not test:
        raise ValueError("All temporal cohorts must be nonempty")
    if max(row["index_date"] for row in train) >= min(row["index_date"] for row in validation) or max(
        row["index_date"] for row in validation
    ) >= min(row["index_date"] for row in test):
        raise ValueError("Temporal cohorts overlap")
    groups = [{row["patient_id"] for row in cohort} for cohort in (train, validation, test)]
    if groups[0] & groups[1] or groups[0] & groups[2] or groups[1] & groups[2]:
        raise ValueError("Patient leakage between cohorts")
    for row in train + validation + test:
        if row["feature_cutoff"] >= row["index_date"] or len(row["features"]) != len(FEATURES):
            raise ValueError("Features must precede the index event and use only the fixed allowlist")


def predict(weights, features):
    terms = [weight * value / scale for weight, value, scale in zip(weights[1:], features, SCALES)]
    return sigmoid(weights[0] + sum(terms)), dict(zip(FEATURES, terms))


def fit(rows, iterations=450):
    weights = [0.0] * 6
    for _ in range(iterations):
        gradient = [0.0] * 6
        for row in rows:
            x = [1.0] + [value / scale for value, scale in zip(row["features"], SCALES)]
            error = sigmoid(sum(a * b for a, b in zip(weights, x))) - row["outcome"]
            for j, value in enumerate(x):
                gradient[j] += error * value
        for j in range(6):
            weights[j] -= 0.6 * (gradient[j] / len(rows) + (0.003 * weights[j] if j else 0))
    return weights


def metrics(rows, scores, threshold):
    labels = [row["outcome"] for row in rows]
    tp = sum(y == 1 and p >= threshold for y, p in zip(labels, scores))
    fp = sum(y == 0 and p >= threshold for y, p in zip(labels, scores))
    positive = sum(labels)
    # Average precision uses recall increments at tied score groups, not trapezoidal interpolation.
    ranked = sorted(zip(scores, labels), reverse=True)
    seen = hits = 0
    ap = 0.0
    for score in sorted(set(scores), reverse=True):
        group = [y for p, y in ranked if p == score]
        hits += sum(group)
        seen += len(group)
        ap += (sum(group) / positive if positive else 0) * hits / seen
    calibration = []
    for bucket in range(5):
        group = [
            (y, p)
            for y, p in zip(labels, scores)
            if bucket / 5 <= p < (bucket + 1) / 5 or (bucket == 4 and p == 1)
        ]
        calibration.append(
            dict(
                lower=bucket / 5,
                upper=(bucket + 1) / 5,
                count=len(group),
                predicted=sum(p for _, p in group) / len(group) if group else None,
                observed=sum(y for y, _ in group) / len(group) if group else None,
            )
        )
    return dict(
        count=len(rows),
        prevalence=positive / len(rows),
        precision=tp / (tp + fp) if tp + fp else 0,
        recall=tp / positive if positive else 0,
        average_precision=ap,
        false_positive_rate=fp / (len(rows) - positive) if len(rows) > positive else 0,
        brier=sum((p - y) ** 2 for y, p in zip(labels, scores)) / len(rows),
        calibration=calibration,
    )


def evaluate():
    rows = examples()
    train, validation, test = rows[:1080], rows[1080:1440], rows[1440:]
    leakage_check(train, validation, test)
    weights = fit(train)
    validation_scores = [predict(weights, row["features"])[0] for row in validation]
    # Select threshold on validation only; freeze before any test inspection.
    choices = []
    for threshold in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        m = metrics(validation, validation_scores, threshold)
        f1 = (
            2 * m["precision"] * m["recall"] / (m["precision"] + m["recall"])
            if m["precision"] + m["recall"]
            else 0
        )
        choices.append((f1, threshold))
    threshold = max(choices)[1]
    scores = [predict(weights, row["features"])[0] for row in test]
    prevalence = sum(row["outcome"] for row in train) / len(train)
    return dict(
        mode="synthetic_only",
        model="logistic_regression",
        seed=360,
        version="synthetic-logistic-v1",
        feature_names=list(FEATURES),
        weights=weights,
        threshold=threshold,
        cohorts={
            name: dict(count=len(cohort), first=cohort[0]["index_date"], last=cohort[-1]["index_date"])
            for name, cohort in [("train", train), ("validation", validation), ("test", test)]
        },
        test=metrics(test, scores, threshold),
        constant_baseline=metrics(test, [prevalence] * len(test), threshold),
        subgroups={
            group: metrics(
                [row for row in test if row["subgroup"] == group],
                [score for row, score in zip(test, scores) if row["subgroup"] == group],
                threshold,
            )
            for group in ("synthetic_group_a", "synthetic_group_b")
        },
        leakage_checks=dict(
            temporal_separation=True,
            patient_separation=True,
            pre_index_features=True,
            threshold_selected_on_validation=True,
            outcome_excluded_from_features=True,
        ),
        limitations=[
            "Artificial data-generating process; no real-world effectiveness claim",
            "No patient triage or prescribing use",
            "Representative approved data and external validation required",
            "Signed log-odds feature contributions, not causal effects or SHAP values",
        ],
    )
