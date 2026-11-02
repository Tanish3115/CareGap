# Development handover

Updated 2 November 2026. All work is local. No GitHub push is authorized. The user selected configurable integrations with local test modes; this handover does not enable external clinical-data processing, real messaging or live ABDM.

## Run and configure

The single-container free demonstration has a separate deployment guide under infra/free-demo. The approved offline knowledge adapter and extraction evaluator are documented in APPROVED_KNOWLEDGE.md and EXTRACTION_VALIDATION.md. Their tests do not confer clinical approval or provide licensed source data.

The refreshed interface uses a persistent desktop sidebar, expandable mobile menu and separate feature sections for each role. The patient overview provides quick actions; uploads return to Documents. Navigation retains drafts while switching sections and supports browser history/direct section links. See INTERFACE_NAVIGATION.md for the complete feature map. The updated frontend was built and refreshed locally; all ten browser flows passed, including accessibility checks across every synthetic patient section and the expanded mobile menu.

The running application is http://localhost:3300, API documentation http://localhost:8001/docs and readiness http://localhost:8001/ready. PostgreSQL uses loopback port 55432. Follow README.md for fresh installation, generated private environment files, migrations and explicit administrator provisioning. Existing Docker data is retained. The original workspace SQLite database and unrelated README.zip are preserved.

Use the navigation selector for exactly Kannada, Telugu, Tamil, Malayalam, English and Hindi. Language selection persists per browser. Each of the five translated catalogs covers all 1003 reference interface entries, including clinical workflow and consent controls. Original clinical/source text stays unchanged. Native-language medical review remains unverified. Local reminder preferences support the same six languages. See LOCALIZATION.md.

## Implemented development workflows

Patients now have deletion controls for documents, consultations, individual follow-ups, medication-use reports and structured records. Deletion uses explicit confirmation, owner/current-version checks and historical dependency guards. Documents use a durable private-file cleanup queue with patient-visible status; pending cleanup blocks account erasure and migration downgrade. The OCR worker retains its read-only mount. See RECORD_DELETION.md for included history, linked-evidence restrictions and retained originals/backups.

- Patient/doctor/admin workspaces, verification, profiles, private validated documents, revocable cookie sessions, scoped patient consent, organization membership guards and audit metadata.
- Source-linked consultations, correction histories, patient-owned permanent consultation deletion, structured clinical/care records, rescheduling, follow-up outcomes and a unified current-record timeline.
- Supervised local PDF/OCR jobs, source-transcription review, exact-source prescription drafts and reviewed historical medication entries. New labelled multiline extraction includes doctor, clinic, source date, follow-up and test context. Missing or ambiguous data remains missing; no automatic prescribing.
- Separate patient medication-use accounts, clinician reconciliation, literal comparison indicators and explicitly synthetic safety fixtures. A clinical knowledge-provider contract is available; no validated real medication database is bundled.
- Recorded care worklists, staff-reviewed interventions, local mock reminders/preferences/history and descriptive outcome extracts. No intervention is automatically applied.
- Authorized source overviews and a bounded HTTP source-selection adapter. External mode requires operator approval and patient opt-in tied to a named processor. It accepts only references to supplied source extracts; invented clinical prose is rejected. Default mode stays local/extractive.
- Bounded FHIR preview/import with retained original JSON; structured and longitudinal R4 exports, including original-document references, consultation accounts, medication distinctions, provenance and patient-owned consent export. Imports do not create permissions. These are local mappings, not general FHIR/ABDM conformance.
- Reproducible artificial-data logistic baseline and optional offline comparisons of logistic regression, gradient boosting, XGBoost and a separately labelled censored AFT outcome. TreeSHAP additivity is checked. No application patient is scored. Optional dependencies are hash-locked separately in research/requirements.lock.txt.
- Operational organization/account management, privacy-review requests, paged personal extracts, backup/restore tools and an isolated HTTPS/shared-Redis rehearsal.
- Offline reviewed-plan patient erasure for current local records/source files, with exact fingerprints, explicit maintenance/policy confirmations, cross-patient/storage guards and recoverable committed receipts. S3 execution is blocked; backups/provider retention and declared pseudonymous/audit metadata remain outside its removal scope. This was tested only on disposable synthetic data. See PRIVACY_ERASURE.md.

## Master-prompt closure additions

The complete source specification and 22-section checklist are in MASTER_PROMPT.md and MASTER_PROMPT_CHECKLIST.md. Newly completed software includes offline exact-alias medication terminology with per-association clinician review, retained catalog evidence and FHIR coding; notification channel adapters; executable registered-study diagnostics with an actual synthetic dashboard report; repeatable accessibility/keyboard/concurrent-read checks; and maintained lint/format/container/source-artifact checks. Native-language review and live/clinical/infrastructure approvals remain explicitly external.

Ordinary request-URL logging is disabled in Uvicorn and Next development mode. Unexpected exceptions return a generic response with a generated request ID; private exception content is not printed. API rollback/source-cleanup tests retain their original integrity assertions under that contract. This work did not execute real patient erasure or enable an external provider.

## Verification

Latest verification on 2 November 2026: full SQLite 270 passed/five environment skips; full PostgreSQL 271 passed/four skips with a clean migration/model comparison. Eleven browser regression flows passed in the expanded run; the new knowledge-evidence flow passed separately after correcting its test navigation to open the comparison details. Together these cover twelve flows; no claim of a single twelve-green run is made. The final 27 targeted knowledge/extraction/free-demo checks also passed, including private-input validation-error redaction. Ruff lint/format passed for 175 Python files, Biome lint/format for 42 frontend source files, TypeScript and locale checks passed with 1003 reference keys. Normal and single-container free-demo images built successfully. CI defines the extra fixture and demo-image checks but has not run remotely.

The isolated free-demo container was exercised at a 512 MB memory/one-CPU limit: registration/login, HttpOnly sessions, PDF upload/download, denied anonymous retrieval, OCR processing and durable file cleanup passed. The translated banner and mobile/Kannada display checks passed. Restart revoked old sessions, removed old registration state and produced an empty document vault. This is a bounded synthetic smoke, not independent capacity or clinical validation. The refreshed local demo is http://127.0.0.1:3600. It has no existing application volume mounts; all data resets on restart.

The normal application remains http://localhost:3300 on schema `0019`. Read-only checks preserve five users, three documents, one consultation, four grants and four requests. All three original source hashes match stored values and the retained backup; no existing application source/record was deleted. The normal stack and isolated HTTPS rehearsal use the refreshed images; no migration beyond `0019` was added in this milestone. No commit, GitHub push, provider activation or public deployment occurred.

Free Render deployment is prepared in render.yaml and infra/free-demo/README.md. Render is not connected, and browser access to Edge was denied by the computer-use tool, so no account or public address was created. An account/connection and authorized publication of current reviewed source or image remain required. The user's explicit no-push instruction persists. The previous pre-migration backup `.tools/backups/20261102T144553Z-723525b6` remains intact and verified.

## Remaining deployment gates

This is a tested development project, not a clinically validated or production-certified system. Remaining gates include native-language medical review, approved terminology/knowledge data, representative clinical/model validation, general external FHIR/ABDM conformance, live provider configuration, managed encryption/keys/monitoring, provider/backup retention and erasure procedures, and independent accessibility, load, security, privacy/legal and institutional review. Privacy-request closure does not erase an account. See DEPLOYMENT_GATES.md and ROADMAP.md.

## Source package

Run `backend/.venv/Scripts/python.exe scripts/package_handover.py` from the root. The verified ZIP and SHA-256 file are written under ignored `.tools/handover`. The package contains source, tests, migrations, locked requirements and documentation. It excludes private configuration, databases, patient files, backups, dependencies, generated build output and Git history. It also scans included files for the configured private credential values before packaging. A source manifest records every included file hash. Packaging rejects unreviewed application data artifacts and permits only the three named synthetic-only research fixtures. Environment settings and backup keys must be transferred separately through the operator's secure procedure.
