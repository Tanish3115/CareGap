# Current implementation progress

Updated 30 October 2026. This supersedes the historical findings/status in `PROJECT_REVIEW.md` where fixes are described below.

## Implemented

- Restored a project-local Python 3.12 environment; preserved the broken old virtual environment and existing SQLite data.
- Saved Git checkpoint `ff7b6bf` before implementation changes.
- Fixed public admin registration, automatic admin clinical access, unverified doctor access, consent-free uploads, unknown-scope fallback, first-grant-only behavior and record-scope bypass.
- Added explicit read/upload permissions, selected-record grants, expiration/revocation and an atomic decision workflow with a unique pending-request constraint.
- Added professional verification history, an operational admin UI, clinician workspace and patient approval/revocation/audit UI.
- Replaced localStorage credentials with HttpOnly cookies and database-backed revocable sessions; added login throttling, origin checks and request-size limits.
- Required configured random signing keys; generated ignored local configuration without exposing secrets.
- Implemented PDF/image content checks, safe path ancestry, upload rollback cleanup and download checksum verification.
- Corrected date-of-birth persistence, optional profile-field clearing, ineffective-grant counts and unavailable care-gap metrics.
- Replaced unsupported encryption/identity verification/clinical analytics marketing with accurate product status.
- Added two explicit Alembic revisions, migration/model comparison and a backup-first legacy SQLite adoption tool.
- Added locked Python requirements with hashes, non-root Docker execution, build-context exclusions, same-origin browser API proxy, readiness checks and a CI workflow.
- Upgraded Next.js/React and compatible tooling after dependency advisories. `npm` reported zero known vulnerabilities after installation.

## Verification record

- Backend: 67 tests passed on SQLite and the same 67 passed on a disposable PostgreSQL database. Coverage includes active login throttling, request-size rejection, upload rollback cleanup, valid images, consent lifecycle, patient isolation, short-code collision retries, finite ID capacity and legacy migration preservation/refusal.
- Migrations: baseline-to-head, preservation of a synthetic existing row, downgrade/re-upgrade and comparison against model metadata passed on SQLite. PostgreSQL upgrade/model checks also passed.
- Browser: 3 Playwright tests passed: patient registration/upload/download/reload/logout/cross-patient denial; anonymous dashboard redirect; verified doctor request/patient approval/access/revocation.
- Frontend: ESLint, TypeScript and an isolated Next.js production build passed. Docker frontend image also built with all application routes.
- Docker: frontend, API and PostgreSQL images built and started successfully. API/PostgreSQL health checks passed; the application is running at http://localhost:3300 and API docs at http://localhost:8001/docs. Both application containers were checked to run as non-root users (UID 999/1001).
- Full-stack browser smoke: registration, PostgreSQL/file persistence after reload, checksum, download, cross-patient denial and session revocation passed against the running Docker stack. Desktop/mobile screenshots were visually inspected, and the 390px mobile viewport had no document-level horizontal overflow.
- Remaining test dependency notice: Starlette warns that its httpx-based TestClient is deprecated. Current tests pass; moving to its replacement is separate maintenance work.

The existing SQLite database still has its original modification time and size; it was not migrated, seeded or tested against during this work. Docker contains only synthetic smoke-test records and independently registered development users.

## Partial and unimplemented requirements

Patient ID usability update: patients now share an ID such as `A123` (one uppercase letter and three digits), and the clinician input displays that example. Migration `0004` converts existing sharing codes without changing UUIDs or linked documents. Unique allocation retries collisions and scans free slots; all 26,000 occupied slots produce a controlled registration error without creating a partial account. Oversized legacy databases are rejected before migration changes any IDs. Consent requests also continue accepting existing UUIDs through the API. The database was backed up before the live update; migration, code-format checks, document-link checks, application and readiness checks passed. All three browser tests passed after precompiling development pages to remove cold-compilation timing from user-action assertions; their authorization assertions were retained.

The current milestone covers the master prompt's first working vertical slice and a functional document-sharing workflow. It is not the complete nine-phase product.

- Medical records: source documents and demographics exist; consultations, structured diagnoses/allergies/labs, correction/version history and clinical timelines remain to implement.
- Consent: document categories and selected documents are supported; verified organizations, tenant isolation and broader clinical-resource scopes remain.
- Document storage: private application-mediated local files and checksums work; S3/MinIO, managed encryption and retention are pending.
- AI: OCR, extraction uncertainty/review, normalization and grounded summaries are pending. No fake AI response is exposed as a real integration.
- Medication intelligence: medication orders/use/dispensing, reconciliation and validated safety-provider integration are pending.
- Care coordination: follow-up/referral/test outcomes, scheduling and mock notification providers are pending.
- Analytics: synthetic baseline training/evaluation, risk explanations and intervention logging/evaluation are pending. No clinical performance or causal effectiveness is claimed.
- Deployment: independent security/clinical/privacy review, organization isolation, managed secrets/encryption, backup restoration exercises, accessibility/performance audits and staging remain.

## Next milestone

Implement source-linked encounters, correction/version history and follow-up tasks with the existing authorization policy and tests, then add an asynchronous document-processing pipeline with an explicit human review boundary. Preserve a working vertical slice at every step, as required by the master prompt.
