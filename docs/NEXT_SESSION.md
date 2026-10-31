# CareGap 360 — next-session handoff

Saved: 31 October 2026, Asia/Calcutta. User requested stopping for today and continuing the remaining work tomorrow (1 November 2026). Do not resume implementation until the user requests it.

## Objective and specification

Continue implementing the supplied CareGap 360 master prompt milestone by milestone, preserving a working application. The product is a patient-controlled longitudinal health-record and care-continuity platform, eventually including prescription extraction, medication reconciliation, care-gap analytics and clinician-reviewed intervention support.

The original master prompt attachment was provided at:
`C:/Users/tanis/.codex/attachments/b889c31d-7976-471a-92bb-25ee9d803e80/Pasted text.txt`.

Read `README.md`, `docs/PROGRESS.md`, `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` before continuing. `docs/PROJECT_REVIEW.md` is a historical review; many listed defects were subsequently fixed.

## Current state

- Functional account, patient-profile, document-vault and patient-consent application; estimated 20–25% of the full master-prompt scope, not a measured completion score.
- Next.js 16.4.3 / React 19 frontend; Python 3.12 / FastAPI / SQLAlchemy backend; PostgreSQL in Docker; local filesystem document storage.
- Registration/login, HttpOnly cookie sessions, server-side session revocation, role restrictions, origin checks and rate limiting.
- Validated PDF/JPG/PNG upload, private authenticated downloads, checksum verification, ownership/consent enforcement and audit events.
- Doctor verification, access requests, patient approval/denial, document-category and selected-record scopes, explicit upload permission, expiration and revocation.
- Basic patient, doctor and operational administrator workspaces.
- Alembic migrations through `0004`; Docker setup, locked dependencies, CI definition and a backup-first legacy SQLite adoption tool.
- No default administrator credentials. Administrators are provisioned explicitly with the CLI documented in README; do not invent credentials or expose secrets.

## User's latest ID preference

Patient-facing sharing IDs must be **one uppercase letter followed by three digits**, e.g. `A123`, `B007`, `A000`.

- The patient dashboard displays this short ID.
- The clinician input shows `e.g. A123`, validates four characters, and normalizes the letter to uppercase.
- Internal UUIDs and document/consent relationships remain unchanged. The API still accepts UUIDs for backward compatibility.
- The namespace has 26,000 unique codes. Allocation handles collisions, scans remaining free slots and rejects exhausted capacity without leaving a partial account.
- Migration `0004` converted existing sharing codes; live checks found zero invalid codes and zero orphaned documents.

Latest code checkpoint: `3289979` — `Use one letter and three digits for patient IDs with unique finite allocation`.

## Latest verification

- 67 backend tests passed on SQLite.
- The same 67 tests passed on a disposable PostgreSQL database; migration/model comparison passed.
- Three Playwright browser tests passed, including registration/upload/download/logout, cross-patient denial and clinician request/patient approval/revocation using short IDs.
- ESLint, TypeScript and Docker production builds passed.
- Initial browser rerun hit Next.js cold-compilation navigation timeouts while builds/tests ran concurrently. Traces confirmed successful registration/login and correct unauthorized responses. The test harness now precompiles its development pages; original functional and authorization assertions remain intact.
- Known maintenance notice: Starlette's httpx-based TestClient emits a deprecation warning; tests currently pass.

Do not rerun checks merely to repeat old results. Run the checks appropriate to the next changes.

## Running and testing

Last verified application URL: `http://localhost:3300`.
API documentation: `http://localhost:8001/docs`.
API readiness: `http://localhost:8001/ready`.
PostgreSQL host port: `55432`.

Check actual runtime state next session; do not assume containers remained running.

```powershell
docker compose up -d
docker compose ps
```

Working host interpreter: `backend/.venv/Scripts/python.exe`. The old `backend/venv` points to a missing interpreter and was preserved. A workspace-local Python runtime also exists under ignored `.tools/python`.

Backend tests, from `backend`:

```powershell
.venv/Scripts/python.exe -m pytest -q
```

PostgreSQL regression, from the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/check_postgres.py
```

This creates and removes only a uniquely named synthetic test database. Never point destructive test fixtures at real clinical data.

Frontend checks, from `frontend`:

```powershell
npm run lint
npm run typecheck
npm run test:e2e
```

Read `frontend/AGENTS.md` and relevant installed Next.js documentation before frontend changes. Browser tests use isolated ports 3100/8100 and disposable synthetic data. `.next-e2e` isolates their build output.

## Data and environment preservation

- The original `backend/caregap360.db` was not modified; the running application uses PostgreSQL.
- Existing Docker accounts, sessions and uploaded files were preserved through ID migrations.
- Root `.env` and `backend/.env` contain generated local secrets and are ignored. Do not print or commit them.
- PostgreSQL backups were made inside the PostgreSQL container before the sharing-code migrations, most recently `/tmp/caregap-before-four-character-ids.dump`. Do not remove volumes or restore over live data casually.
- An ignored `backend/wheelhouse` holds verified Linux wheels because dependency downloads were slow. Docker can install these offline with required hashes. Fresh checkouts download from locked requirements normally.
- Git operations need the existing safe-directory override and may require filesystem escalation. Do not include `.env`, patient files, virtual environments, `.tools`, generated build output or wheel binaries in commits.

## Resume here

Next milestone: **source-linked consultation/encounter records, chronological medical timeline, correction/version history and follow-up tasks**, using the existing shared authorization policy and meaningful positive/negative tests.

Then proceed to:

1. Private object-storage abstraction and reliable asynchronous processing with visible failure/retry states.
2. OCR/prescription extraction, uncertainty, normalization and an editable human-verification boundary.
3. Structured medication histories, reconciliation and a validated safety-provider interface.
4. Follow-up/referral/test outcomes, scheduling and mock notification providers.
5. Synthetic-data baseline analytics and properly evaluated risk explanations.
6. Intervention event logging and reviewed rules before causal-effect claims.
7. Source-grounded summaries, FHIR adapters, optional ABDM preparation and deployment hardening.

These advanced modules are not currently implemented. Do not label synthetic demonstrations as validated clinical services or claim production, clinical or legal certification. Preserve patient consent, original sources, auditability and clear verification status throughout.
