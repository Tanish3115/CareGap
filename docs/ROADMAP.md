# Implementation roadmap

Updated 30 October 2026. The first patient vertical slice and document-sharing workflow are implemented. See [PROGRESS.md](PROGRESS.md) for executed verification; the full master-prompt product remains incremental work.

| Master phase | Status | Remaining work and measurable acceptance |
| --- | --- | --- |
| 1: foundation | Core implemented | Python/Next.js runtime, authentication, three role-aware workspaces, migrations, Docker and tests exist. Complete organization/user lifecycle administration and a reusable synthetic seed command. |
| 2: medical records | Document vertical slice implemented | Extend demographics/documents to encounters, diagnoses, allergies, structured labs, referrals, timeline, correction/version history and private object storage. Every record must retain source/author/verification provenance and pass cross-patient denial tests. |
| 3: prescription extraction | Pending | Add reliable queue, OCR/extraction interfaces, original text/image references, uncertainty, normalization and editable human review. Test unclear handwriting, missing strength, similar names, conflicting dates and wrong patient association; no unreviewed value may become trusted medication data. |
| 4: access and consent | Document workflow implemented | Professional verification history, doctor requests, patient decisions, record/category scopes, upload permission, expiration, revocation and audit UI work. Extend to verified organizations, clinical-resource scopes and tenant isolation with positive/negative integration tests. |
| 5: medication intelligence | Pending | Separate orders/dispensing/reported use/confirmed use; add reconciliation events and source comparison. Test duplicates/overlaps/contradictions/incomplete instructions. Use a validated knowledge provider or explicitly synthetic demonstration adapter, with evidence and clinician review. |
| 6: care-gap analytics | Pending | First capture appointment/referral/test/follow-up events and outcomes. Build reproducible synthetic baselines with temporal holdout, PR-AUC, calibration, false-positive rates, subgroup evaluation and leakage checks. Clearly label synthetic results. |
| 7: intervention intelligence | Pending | Record intervention assignment, reason, staff reviewer, timing, outcome and missingness. Start with reviewed rules. Write an evaluation protocol addressing confounding and selection bias; do not describe correlations as individual treatment effects. |
| 8: advanced integrations | Pending | Add source-grounded summaries over authorized records, explicit fact/reported/uncertain categories, FHIR adapters with tests, multilingual accessibility, mock notification providers/preferences/delivery history and monitoring. ABDM remains preparation until actual authorization/conformance. |
| 9: hardening/deployment | Partial | Security regressions, browser tests, locked dependencies, non-root images and CI definition exist. Add independent security/privacy/clinical review, encryption/key management, retention/deletion, restore exercises, accessibility/performance checks, staging and shared rate-limit storage. |

## Next dependency-ordered tasks

1. Add source-linked encounters, correction/version history and follow-up tasks under the existing authorization policy.
2. Add private object-storage abstraction and reliable processing jobs with visible retry/failure states.
3. Add OCR/extraction and review of untrusted values; do not invent clinical data or bypass verification.
4. Build medication reconciliation before safety assistance or risk-model integration.
5. Capture representative outcomes before claiming predictive or causal effectiveness.

Every milestone must preserve a working application and add meaningful tests. Passing software checks does not establish clinical validity, production certification or legal compliance.
