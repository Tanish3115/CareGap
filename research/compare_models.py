"""Offline, reproducible artificial-data comparison. Never loads application data."""

import argparse
import json
import math
import random
from importlib.metadata import version
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import numpy as np
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[1]
# Load only the pure baseline module, avoiding service-package initialization,
# application settings, storage clients and database access in this offline tool.
spec = spec_from_file_location("caregap_synthetic_baseline", ROOT / "backend/app/services/synthetic_risk.py")
baseline = module_from_spec(spec)
spec.loader.exec_module(baseline)
FEATURES, SCALES = baseline.FEATURES, baseline.SCALES
examples, leakage_check, metrics = baseline.examples, baseline.leakage_check, baseline.metrics


def threshold_on_validation(rows, scores):
    candidates = []
    for threshold in (0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8):
        result = metrics(rows, scores, threshold)
        precision, recall = result["precision"], result["recall"]
        candidates.append(
            (2 * precision * recall / (precision + recall) if precision + recall else 0, threshold)
        )
    return max(candidates)[1]


def evaluate(seed=360):
    rows = examples(seed=seed)
    train, validation, test = rows[:1080], rows[1080:1440], rows[1440:]
    leakage_check(train, validation, test)

    def X(cohort):
        return np.array([row["features"] for row in cohort], dtype=float)

    def y(cohort):
        return np.array([row["outcome"] for row in cohort], dtype=int)

    models = {
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(max_iter=1000, random_state=seed)
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=80, max_depth=2, learning_rate=0.05, random_state=seed
        ),
        "xgboost": xgb.XGBClassifier(
            n_estimators=80,
            max_depth=2,
            learning_rate=0.05,
            random_state=seed,
            n_jobs=1,
            eval_metric="logloss",
        ),
    }
    report = {}
    for name, model in models.items():
        model.fit(X(train), y(train))
        threshold = threshold_on_validation(validation, model.predict_proba(X(validation))[:, 1].tolist())
        scores = model.predict_proba(X(test))[:, 1].tolist()
        result = metrics(test, scores, threshold)
        # Check the application's explicit metric implementation against independent references.
        assert abs(result["average_precision"] - average_precision_score(y(test), scores)) < 1e-12
        assert abs(result["brier"] - brier_score_loss(y(test), scores)) < 1e-12
        report[name] = dict(
            threshold=threshold,
            test=result,
            subgroups={
                group: metrics(
                    [row for row in test if row["subgroup"] == group],
                    [score for row, score in zip(test, scores) if row["subgroup"] == group],
                    threshold,
                )
                for group in ("synthetic_group_a", "synthetic_group_b")
            },
        )
    booster = models["xgboost"].get_booster()
    sample = xgb.DMatrix(X(test[:3]), feature_names=None)
    contributions = booster.predict(sample, pred_contribs=True)
    margins = booster.predict(sample, output_margin=True)
    assert np.allclose(contributions.sum(axis=1), margins, atol=1e-5)

    # A separate artificial time-to-completion outcome with explicit right censoring.
    rng = random.Random(seed + 1)
    durations, observed, events = [], [], []
    for row in rows:
        scaled = [value / scale for value, scale in zip(row["features"], SCALES)]
        duration = math.exp(2.1 + 1.6 * scaled[0] + 0.5 * scaled[4] + rng.gauss(0, 0.6))
        censor = rng.uniform(20, 100)
        durations.append(duration)
        observed.append(min(duration, censor))
        events.append(duration <= censor)
    matrices = []
    for start, end in ((0, 1080), (1080, 1440), (1440, 1800)):
        matrix = xgb.DMatrix(X(rows[start:end]))
        matrix.set_float_info("label_lower_bound", observed[start:end])
        matrix.set_float_info(
            "label_upper_bound",
            [time if event else float("inf") for time, event in zip(observed[start:end], events[start:end])],
        )
        matrices.append(matrix)
    aft = xgb.train(
        dict(
            objective="survival:aft",
            eval_metric="aft-nloglik",
            aft_loss_distribution="normal",
            aft_loss_distribution_scale=0.8,
            tree_method="hist",
            max_depth=2,
            eta=0.05,
            seed=seed,
            nthread=1,
        ),
        matrices[0],
        num_boost_round=80,
    )
    mu = aft.predict(matrices[2], output_margin=True).tolist()
    horizon = 30
    eligible = [i for i in range(360) if events[1440 + i] or observed[1440 + i] >= horizon]
    horizon_rows = [{**test[i], "outcome": int(observed[1440 + i] > horizon)} for i in eligible]
    delay = [1 - 0.5 * (1 + math.erf((math.log(horizon) - mu[i]) / (0.8 * math.sqrt(2)))) for i in eligible]
    pairs = [
        (i, j)
        for i in range(360)
        for j in range(360)
        if events[1440 + i] and observed[1440 + i] < observed[1440 + j]
    ]
    concordance = (
        sum(1 if mu[i] < mu[j] else 0.5 if mu[i] == mu[j] else 0 for i, j in pairs) / len(pairs)
        if pairs
        else None
    )
    survival = dict(
        model="xgboost_aft",
        target="time_to_artificial_care_completion",
        horizon_days=horizon,
        test_count=360,
        observed_events=sum(events[1440:]),
        right_censored=360 - sum(events[1440:]),
        horizon_known=len(eligible),
        horizon_unknown_excluded=360 - len(eligible),
        horizon_metrics=metrics(horizon_rows, delay, 0.5),
        concordance_index=concordance,
        limitations="Separate target; not directly comparable to missed-follow-up classification. Horizon metrics exclude early-censored cases and are unadjusted, not IPCW estimates.",
    )
    return dict(
        mode="synthetic_only",
        version="synthetic-model-comparison-v1",
        seed=seed,
        packages={name: version(name) for name in ("numpy", "scikit-learn", "xgboost-cpu")},
        feature_names=list(FEATURES),
        cohorts=dict(train=1080, validation=360, test=360),
        classification=report,
        survival=survival,
        tree_shap=dict(
            model="xgboost",
            scale="raw_log_odds",
            additive_check_passed=True,
            examples=[
                dict(
                    features=dict(zip(FEATURES, row["features"])),
                    contributions=dict(zip(FEATURES, values[:-1].tolist())),
                    bias=float(values[-1]),
                    output_margin=float(margin),
                )
                for row, values, margin in zip(test[:3], contributions, margins)
            ],
        ),
        leakage_checks=dict(
            temporal_separation=True,
            patient_separation=True,
            pre_index_features=True,
            thresholds_selected_on_validation=True,
            fixed_model_hyperparameters=True,
        ),
        limitations=[
            "Artificial examples only; no clinical effectiveness claim",
            "No application database or patient scoring",
            "Test metrics are reported after training; no model selected for patient care",
            "TreeSHAP contributions explain model output, not causal effects",
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "backend/app/data/synthetic_models.json")
    args = parser.parse_args()
    result = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            dict(
                mode=result["mode"],
                models=list(result["classification"]),
                survival=result["survival"]["model"],
                tree_shap_additive_check=True,
                output=str(args.output),
            )
        )
    )
