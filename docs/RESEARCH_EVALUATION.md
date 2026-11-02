# Synthetic risk baseline and intervention evaluation protocol

1 November 2026. Software integration/evaluation only. No real-patient effectiveness, treatment effect or clinical validation is claimed.

## Executed synthetic baseline

Run `backend/.venv/Scripts/python.exe scripts/evaluate_synthetic.py` from the repository root. A fixed seed produces 1,800 artificial, patient-disjoint records with five pre-index features: prior missed visits, prior incomplete referrals, days since visit, scheduling lead time and reported barrier count. Labels are sampled from a stated artificial logistic process. This is not a representative training dataset.

The implementation fits a regularized logistic baseline using training labels. Cohorts are separated chronologically: 1,080 training examples, 360 validation examples, 360 held-out test examples. Threshold selection uses validation only; tests reject overlapping time/patient cohorts and features at/after the index date. A constant training-prevalence baseline is evaluated too. Metrics include precision, recall, average precision, false-positive rate, Brier score, calibration bins and two artificial subgroup summaries. Average precision uses tied-score recall increments, consistent with the [standard metric definition](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html).

The generated artifact is `backend/app/data/synthetic_risk.json`. On the executed seed the held-out average precision is approximately 0.560, precision 0.457, recall 0.800, false-positive rate 0.475 and Brier score 0.193. These are measured artificial-example results, not clinical performance. High false-positive rates remain visible. The UI shows model/baseline metrics, cohorts, calibration, subgroup results and signed log-odds feature contributions. Those contributions are not SHAP values or causal effects. The research API rejects patient identifiers and never automatically scores patient records.

Optional offline comparisons of logistic regression, gradient boosting, XGBoost and a separately labelled censored AFT outcome are implemented in research/compare_models.py. TreeSHAP additivity is checked and the artifact reproduced byte-for-byte in its locked environment. Representative approved labels, external/prospective clinical validation and thresholds matched to actual workflow burden remain external research gates.

## Intervention protocol

Interventions log the staff reviewer, action, target care revision, assignment state, named staff (if assigned), timestamp, outcome/missingness, source revision and optional evaluation reference. The target must belong to the same patient. Later target changes are flagged. Rules suggest outreach, rescheduling or permitted barrier support for staff review; they do not make high-impact interventions automatically.

The observed-outcomes view returns paged source-linked events and unadjusted action counts. Only documented care outcomes occurring after assignment enter completed/missed counts. Pending/unknown/cancelled or pre-assignment outcomes remain excluded/unresolved. Repeated targets are reported. Counts are descriptive, never estimated treatment effects.

Before any causal study:

1. Obtain institutional, clinical, privacy and research approvals; define the eligible population, permitted interventions, index/assignment times and a prespecified outcome window.
2. Preserve both offered and received interventions, declined offers, reasons, co-interventions, baseline access barriers, past attendance and missing outcomes. Record changes after assignment separately.
3. Prefer an approved prospective randomized design when ethical and feasible. Register allocation, intention-to-treat estimand, sample-size/precision requirements, subgroup analyses, monitoring and stopping procedures before looking at outcomes.
4. For observational analyses, prespecify confounders, a causal diagram, overlap/positivity checks, intervention selection/missingness models, sensitivity analyses and external review. Doubly robust estimates or causal forests cannot fix unmeasured confounding by themselves.
5. Separate historical model development from prospective outcome evaluation. Never use post-assignment information as baseline features or choose policies based on held-out outcomes.
6. Require staff oversight and approved consent/preferences for outreach. Contextual bandits and individual treatment-effect recommendations remain unimplemented pending appropriate data and governance.

The event schema, descriptive view and this protocol are available; a validated causal model or randomized clinical experiment is not.

## Executable registered-study evaluator

The offline study evaluator and dashboard fixture now implement registration/timing checks, strict pseudonymous input schemas, assigned-arm counts, receipt/missingness, binary-outcome sensitivity bounds and limited randomized-fixture estimates. It rejects post-assignment features and does not turn missing outcomes into failure or observational differences into causal effects. See INTERVENTION_STUDIES.md and test_intervention_study.py. It does not allocate patients or train an individualized treatment policy.
