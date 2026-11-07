# Remaining implementation work

7 November 2026 audit: the local milestones below are implemented with the stated limits. The explicit remaining hosting copy-tool gap is now closed by the verified resumable command in STORAGE_MIGRATION.md. Execution against an approved private provider, broader clinical validation and the external gates below remain pending; the full master prompt is not declared complete. Current test evidence is recorded at the top of PROGRESS.md.

1 November 2026. Implement and verify locally; do not push or deploy externally.

Work in dependency order, preserving source provenance, consent, version history and a working app:

1. Structured diagnoses, allergies, labs, referral/test/appointment outcomes, dated medication orders/dispensing/confirmed-use records.
2. Care-gap worklist, patient rescheduling, staff-reviewed interventions, local mock notifications/preferences/delivery history.
3. Medication comparison indicators and provider boundary with explicitly synthetic safety demonstrations; no inferred dosing or terminology.
4. Source-grounded summary and tested FHIR adapters, with explicit limits on resource mappings.
5. Reproducible synthetic risk baseline, temporal evaluation, calibration, subgroup/leakage checks and intervention evaluation protocol.
6. Operational organization/user administration, synthetic seed tooling, backup/restore exercise, staging configuration and hardening checks.
7. Full regression, production build, local migration/data-preservation checks and accurate documentation.

External completion gates must remain visible: representative approved data/clinical evaluation, validated medication terminology/knowledge, live messaging credentials/privacy consent, ABDM authorization/conformance, independent security/privacy/legal review, managed deployment/encryption infrastructure. Passing software tests cannot satisfy these gates.

Implemented in this work: steps 1–2 local workflows, literal/synthetic step 3, extractive/bounded step 4, synthetic baseline/protocol and optional additional model comparisons in step 5, operational/backup/TLS rehearsal step 6 and local regression/build/migration checks in step 7. Nine resource-scoped consent groups, a unified current-record timeline, source-bound processor assistance with patient opt-in, all 937 interface entries in the five selected translation catalogs and a guarded offline local erasure operator are also implemented. This does not complete external clinical/causal validation, native-language medical review, general FHIR/ABDM conformance, approved provider/backup retention procedures or managed production infrastructure. See DEPLOYMENT_GATES.md and ROADMAP.md.
