# Reported medication use and reconciliation

Local development milestone, 31 October 2026. No GitHub push is authorized.

Historical `documented_prescription` entries describe source prescriptions. `MedicationUse` is a separate patient-owned account of use on a stated date: taking, not taking or unknown. It does not infer current use from a prescription, issue orders or record dispensing. Names, dose and frequency remain literal reported text; missing values stay null. Multiple reports are not automatically merged or normalized.

Only the patient owner can create/correct an account. Revisions retain the date, reported details, optional historical prescription entry, reason and author. Sources must belong to that patient. A correction compares the expected report version and preserves all earlier versions. The source selector offers latest clinician-confirmed prescription entries; already linked older entries remain accessible with superseded/source-change flags.

Verified clinicians with explicit clinical write consent can add a separate reconciliation assessment: account reviewed, discrepancy or needs clarification. Each assessment references the exact report revision and snapshots the linked historical source and its current versions. Checking the comparison and a note are required. The report and source values are never overwritten by reconciliation, and an assessment is not a medication-safety verification or new prescription.

Report and review version checks serialize competing saves. Linked source versions must match the comparison the clinician loaded; a source-row lock prevents changes during reconciliation. Later patient corrections, source transcriptions, confirmations or pending drafts flag the earlier review as stale. Earlier report and clinician snapshots remain available in paginated history.

Reads/history require patient ownership or a verified clinician's active unrestricted clinical read grant; reconciliation also needs clinical write permission. Document-only/category grants, administrators, other patients, expired/revoked grants and unverified doctors are denied. Consent request/approval wording includes medication accounts, prescription entries and reconciliation. This module uses the existing `include_clinical_records` permission; granular medication-only sharing remains future work. Audits commit transactionally with writes.

API under `/api/v1/clinical/medication-use`:

- `GET ?patient_id=…&limit=20&offset=0`, `POST` a patient report.
- `PUT /{id}` correct a report with `expected_version`.
- `GET /{id}/history` view patient revisions.
- `POST /{id}/reconciliation` append an assessment with expected report/review and linked source versions.
- `GET /{id}/reconciliation/history` view immutable clinician assessments/source snapshots.

Migration `0010` adds three tables without changing existing prescription or clinical rows. Browser workflows cover unknown-use reporting, correction history, source comparison, discrepancy review, later stale review and revocation. Backend tests cover missing details, role/patient isolation, wrong-patient sources, expected versions, expired/revoked grants, unverified doctors and preservation of historical prescriptions.

Remaining: terminology normalization, explicit new orders/dispensing/confirmed-use events, automatic duplicate/overlap analysis with appropriate evidence, validated medication knowledge providers, organization isolation and independent clinical/production review. This is a manual reconciliation foundation, not a clinically validated decision-support engine.
