# CareGap 360 — next-session handoff

Updated: 31 October 2026, Asia/Calcutta. The user resumed implementation after publishing the project to GitHub. The consultation/timeline/history/follow-up milestone is now implemented; continue from the next milestone below when requested.

## Objective and specification

Continue implementing the supplied CareGap 360 master prompt milestone by milestone, preserving a working application. The product is a patient-controlled longitudinal health-record and care-continuity platform, eventually including prescription extraction, medication reconciliation, care-gap analytics and clinician-reviewed intervention support.

The original master prompt attachment was provided at:
`C:/Users/tanis/.codex/attachments/b889c31d-7976-471a-92bb-25ee9d803e80/Pasted text.txt`.

Read `README.md`, `docs/PROGRESS.md`, `docs/ARCHITECTURE.md` and `docs/ROADMAP.md` before continuing. `docs/PROJECT_REVIEW.md` is a historical review; many listed defects were subsequently fixed.

## Current state

- Functional account, patient-profile, document-vault, patient-consent and source-linked clinical-record application. The full master-prompt scope remains incremental; no measured completion percentage is claimed.
- Next.js 16.4.3 / React 19 frontend; Python 3.12 / FastAPI / SQLAlchemy backend; PostgreSQL in Docker; local filesystem document storage.
- Registration/login, HttpOnly cookie sessions, server-side session revocation, role restrictions, origin checks and rate limiting.
- Validated PDF/JPG/PNG upload, private authenticated downloads, checksum verification, ownership/consent enforcement and audit events.
- Doctor verification, access requests, patient approval/denial, document-category and selected-record scopes, explicit upload permission, expiration and revocation.
- Basic patient, doctor and operational administrator workspaces.
- Source-linked consultation notes, chronological document/consultation timeline, attributed correction history, stale-edit protection and consultation-linked follow-up tasks/outcomes.
- Separate explicit clinical read/write consent, disabled for old document grants. Clinical sharing requires unrestricted all-category document consent and includes revision history. Document upload remains a separate action. Patient corrections are patient-reported, retaining prior clinician entries.
- Alembic migrations through `0005`; Docker setup, locked dependencies, CI definition and a backup-first legacy SQLite adoption tool with a fixed baseline schema check.
- No default administrator credentials. Administrators are provisioned explicitly with the CLI documented in README; do not invent credentials or expose secrets.

## User's latest ID preference

Patient-facing sharing IDs must be **one uppercase letter followed by three digits**, e.g. `A123`, `B007`, `A000`.

- The patient dashboard displays this short ID.
- The clinician input shows `e.g. A123`, validates four characters, and normalizes the letter to uppercase.
- Internal UUIDs and document/consent relationships remain unchanged. The API still accepts UUIDs for backward compatibility.
- The namespace has 26,000 unique codes. Allocation handles collisions, scans remaining free slots and rejects exhausted capacity without leaving a partial account.
- Migration `0004` converted existing sharing codes; live checks found zero invalid codes and zero orphaned documents.

Previous ID checkpoint: `3289979`. GitHub repository: `https://github.com/Tanish3115/CareGap`; local `master` tracks `origin/main`. Use `git log -1` for the latest milestone checkpoint.

## Latest verification

- 88 backend tests passed in the full SQLite run, then 2 targeted checks passed for the added legacy-grant migration test and expanded clinical read-only permissions.
- 89 tests passed on a disposable PostgreSQL database; migration/model comparison passed.
- All 5 Playwright browser tests passed with exit status 0: original document/auth/consent flows, patient source-linked consultation/correction/history/follow-up outcome, and explicit clinical approval/clinician writing/revocation. Restricted Windows process cleanup hung after reporting results; the successful final suite ran outside that sandbox with normal Windows process permissions.
- ESLint, TypeScript and Docker production builds passed.
- This milestone's browser tests caught implicit form labels incorporating prefilled textarea/option/help text. Explicit label associations fixed exact accessible-name matching without weakening the assertions. A previous milestone added route precompilation for cold starts; preserve it.
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
- PostgreSQL backups were made inside the PostgreSQL container before migrations, most recently `/tmp/caregap-before-clinical-records-20261031.dump`. Migration `0005` is applied and the local stack is healthy. Do not remove volumes or restore over live data casually.
- An ignored `backend/wheelhouse` holds verified Linux wheels because dependency downloads were slow. Docker can install these offline with required hashes. Fresh checkouts download from locked requirements normally.
- Git operations need the existing safe-directory override and may require filesystem escalation. Do not include `.env`, patient files, virtual environments, `.tools`, generated build output or wheel binaries in commits.

## Resume here

Next milestone: **private object-storage abstraction and reliable asynchronous document-processing jobs with visible failure/retry states**. Read `docs/CLINICAL_RECORDS.md` for the new clinical model and consent decisions. Preserve original sources, append-only attributed corrections, consent boundaries and the working application.

Then proceed to:

1. Structured diagnoses/allergies/labs and referral/appointment outcomes, retaining the same provenance and consent rules.
2. OCR/prescription extraction, uncertainty, normalization and an editable human-verification boundary.
3. Structured medication histories, reconciliation and a validated safety-provider interface.
4. Follow-up/referral/test outcomes, scheduling and mock notification providers.
5. Synthetic-data baseline analytics and properly evaluated risk explanations.
6. Intervention event logging and reviewed rules before causal-effect claims.
7. Source-grounded summaries, FHIR adapters, optional ABDM preparation and deployment hardening.

These advanced modules are not currently implemented. Do not label synthetic demonstrations as validated clinical services or claim production, clinical or legal certification. Preserve patient consent, original sources, auditability and clear verification status throughout.
