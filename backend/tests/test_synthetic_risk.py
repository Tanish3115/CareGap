import pytest
from app.services.synthetic_risk import examples, leakage_check, metrics, fit, predict


def test_metrics_ties_and_constant_prediction_are_well_defined():
    rows = [dict(outcome=y) for y in [1, 0, 1, 0]]
    result = metrics(rows, [0.5] * 4, 0.5)
    assert result["average_precision"] == 0.5 and result["precision"] == 0.5
    assert result["recall"] == 1 and result["false_positive_rate"] == 1 and result["brier"] == 0.25
    assert sum(bucket["count"] for bucket in result["calibration"]) == 4


def test_temporal_patient_and_feature_leakage_are_rejected():
    rows = examples(count=12)
    leakage_check(rows[:4], rows[4:8], rows[8:])
    with pytest.raises(ValueError, match="Temporal"):
        leakage_check(rows[4:8], rows[:4], rows[8:])
    rows[8]["patient_id"] = rows[0]["patient_id"]
    with pytest.raises(ValueError, match="Patient leakage"):
        leakage_check(rows[:4], rows[4:8], rows[8:])
    rows[8]["patient_id"] = "different"
    rows[8]["feature_cutoff"] = rows[8]["index_date"]
    with pytest.raises(ValueError, match="Features"):
        leakage_check(rows[:4], rows[4:8], rows[8:])


def test_baseline_fits_actual_labels_reproducibly_and_explanations_sum():
    rows = examples(count=200)
    weights = fit(rows, iterations=100)
    assert weights == fit(rows, iterations=100)
    probability, terms = predict(weights, [2, 1, 30, 10, 2])
    assert 0 < probability < 1 and len(terms) == 5
    import math

    assert math.log(probability / (1 - probability)) == pytest.approx(weights[0] + sum(terms.values()))
