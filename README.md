# CareGap 360

Hosting preparation for Vercel, Render, Supabase and TLS Redis is documented in [HOSTING_HANDOVER.md](docs/HOSTING_HANDOVER.md). Configuration templates and local migration tooling are ready; public deployment and transfer of existing records have not been performed. The GitHub publication commands and their meanings are documented in [GITHUB_COMMANDS.md](docs/GITHUB_COMMANDS.md).

Patient-controlled medical documents and care-continuity workflows, with source history, scoped sharing and professional verification. Use synthetic data only until the required clinical, privacy, security and operational reviews are completed.

## Free demo deployment

An earlier source snapshot is published separately on [`deploy/free-demo`](https://github.com/Tanish3115/CareGap/tree/deploy/free-demo). Current application source is maintained on `main`; the demo branch is retained. [Open the Render deployment setup](https://render.com/deploy?repo=https%3A%2F%2Fgithub.com%2FTanish3115%2FCareGap%2Ftree%2Fdeploy%2Ffree-demo) and sign in to create the free, disposable service. A hosted public URL has not yet been created; records in this demo reset on restart. Credentials and patient records are excluded from source publication.

## Working functionality

Free demo hosting is prepared in [render.yaml](render.yaml) and the [single-container deployment guide](infra/free-demo/README.md). It runs independently of the normal app and resets synthetic data on restart. Creating the public service still requires a hosting account and a separate deployment step. Publishing source to GitHub does not deploy a public service.

The dashboard now uses a desktop sidebar and mobile menu with focused sections, an overview and quick actions. Documents, consultations, medications, health records, care/reminders, sharing, profile and privacy controls have their own destinations. Clinicians and administrators have menus suited to their roles. Switching sections preserves open drafts. See [navigation and feature locations](docs/INTERFACE_NAVIGATION.md).

Patients can delete uploaded documents, consultations, individual follow-ups, medication-use reports and structured health/care records with explicit confirmation. Version checks and source-dependency guards prevent silent removal of linked evidence. Document files use a durable background cleanup queue with patient-visible receipts; backups and retained imported originals have separate retention rules. See [deletion controls and scope](docs/RECORD_DELETION.md).

The medication comparison now supports a disabled-by-default [approved offline pair-evidence adapter](docs/APPROVED_KNOWLEDGE.md), with pinned data, current reviewed coding and explicit coverage gaps. [Offline extraction evaluation](docs/EXTRACTION_VALIDATION.md) provides reproducible field/error metrics for synthetic or independently approved annotated cases. Neither mechanism supplies clinical approval or a safety clearance.

Language choices: **Kannada, Telugu, Tamil, Malayalam, English and Hindi**. Each translated interface catalog covers all 1003 reference entries. Clinical source text stays unchanged. Native clinical-language review remains a deployment requirement. See [language coverage](docs/LOCALIZATION.md).

- Patient and pending-doctor registration; bcrypt passwords; expiring JWT sessions with server-side revocation.
- Browser authentication using HttpOnly, SameSite cookies. Credentials are not stored in localStorage.
- Patient profile viewing/editing, including date of birth and clearing optional fields.
- PDF/JPG/PNG uploads with actual content validation, size limits, source metadata and SHA-256 checks on download.
- Patient-owned record library with search, category filters, authenticated downloads and explicit unverified status.
- Verified doctor access requests with purpose, duration, document category and optional upload permission.
- Simple patient sharing IDs such as `A123` (one uppercase letter and three digits), displayed on the patient dashboard and accepted in the doctor's access-request field. The field shows an example; existing UUIDs remain internal and continue to work through the API. This format provides 26,000 unique IDs, from `A000` through `Z999`.
- Patient approval/denial, optional selected-document sharing, grant expiration and revocation.
- Doctor workspace listing only authorized patients and records; uploads only with explicit permission.
- Administrator professional verification queue and operational audit metadata. Administrators have no automatic clinical-record access, and public registration cannot create administrators.
- Patient-visible audit history, bounded requests, authentication throttling and deny-by-default authorization.
- Source-linked consultations, a searchable chronological document/consultation timeline, and attributed correction history with stale-edit protection.
- Follow-up tasks linked to consultations, due dates, overdue indicators, completion/cancellation reports and retained outcome history.
- Separate, explicit clinical viewing and editing consent for verified doctors. Existing document-only grants do not share consultations or follow-ups.
- Nine selectable clinical groups; patients can narrow a request before approval. Summaries, histories, medication comparisons, imports/exports and workspaces enforce the approved groups.
- A unified medical timeline across documents, consultations, structured records, care plans, medication accounts and source reviews, with search, dates, sources and version histories.
- Private S3-compatible storage adapter with per-document routing; existing local uploads stay accessible. Optional MinIO development service and actual private-object integration checks.
- Local OCR for printed images/scanned PDFs with page references, engine confidence/uncertainty flags and an editable, versioned source-transcription review.
- Source-bound prescription drafts, manual field editing, missing-value handling and clinician-only confirmation of historical prescription entries, with version history and consent checks.
- Patient-reported medication use, optional historical-prescription comparisons and separate clinician reconciliation assessments with retained history and stale-review flags.
- Structured diagnoses, recorded allergies/reactions, literal lab results, appointments/referrals/tests, outcome histories and clinician-reviewed rescheduling requests.
- Separate clinician-recorded medication orders, dispensing/use accounts and staff-reviewed interventions, with version-bound care links.
- Care worklist, local mock reminders in all six supported languages, patient preferences and delivery history; no real messages are sent.
- Source-linked extractive overview, literal medication comparison indicators, a bounded FHIR R4 preview/import/export workflow and an explicitly synthetic risk-model lab.
- Verified organizations and membership-bound patient grants, account activation/session revocation, operational metrics, patient data extracts and privacy-review requests.
- Isolated synthetic seeding, backup/restore tooling and a separate local HTTPS/shared-Redis rehearsal.
- Alembic migrations, isolated backend tests, PostgreSQL regression checks, Playwright browser tests and a CI workflow.

The [master-prompt checklist](docs/MASTER_PROMPT_CHECKLIST.md) traces all 22 specification sections, including explicit bounded/optional/external requirements. The full master prompt is not yet production-complete. Approved terminology/knowledge providers, broader evaluated extraction, general FHIR/ABDM conformance, native clinical-language review, representative clinical models and governed causal studies remain. External source-selection assistance has a configurable adapter with named-processor patient consent; local extraction remains the default. Real messaging, managed encryption/key infrastructure, provider/backup retention procedures and independent clinical/privacy/security review also remain. Current model/safety demonstrations use artificial data only; summaries select exact source extracts. See [deployment gates](docs/DEPLOYMENT_GATES.md), [progress](docs/PROGRESS.md) and [roadmap](docs/ROADMAP.md).

## Clinical records, care and review support

Use **Unified medical timeline** to search current authorized records across the clinical workspaces, filter by type/date, open sources and inspect earlier versions. Doctors request specific clinical groups and patients may approve a smaller set. Original documents remain under the separately disclosed all-document consent; group selection does not redact source files. See [clinical consent and timeline behavior](docs/CONSENT_SCOPES.md).

Use **Clinical records & care events** to add diagnoses, allergies, literal lab results or dated care plans with sources, reasons and correction history. Verified clinicians with explicit clinical write permission can also record medication events and interventions. Patients can request rescheduling; clinician decisions keep their reviewer and history. These are documented plans/accounts, not bookings with external providers.

Use **Care coordination & source overview** for the recorded care worklist, opt-in local reminders, cited record extracts, medication comparisons, FHIR subset exchange and the synthetic risk model lab. FHIR import requires a preview, matching patient UUID and source confirmation; original JSON is retained. Safety indicators are literal comparisons or separately marked artificial fixtures, never a real medication clearance. See [clinical extensions](docs/CLINICAL_EXTENSIONS.md) and [research evaluation](docs/RESEARCH_EVALUATION.md).

Operational administrators can verify organizations/memberships, manage account activation and review privacy-request metadata. Organization membership alone grants no medical access. **Privacy & personal data requests** provides patient-owned paged record extracts and administrative review requests; submitting or closing an erasure request does not itself erase records.

An explicit offline [erasure operator](docs/PRIVACY_ERASURE.md) supports reviewed local patient/source removal with policy references, fingerprint checks, maintenance confirmations and recoverable receipts. It retains declared pseudonymous/audit metadata, blocks S3 execution and does not erase backups. No existing application data was erased during development.

## Consultations and follow-ups

The patient dashboard includes **Medical timeline & follow-ups**. Add a consultation with a date, notes and optional original documents. Open it to download sources, record a correction, view every earlier version or add a follow-up. Follow-ups support rescheduling, completion, cancellation and reopening, with an attributed reason for each update. Patient edits are labeled patient-reported; doctor entries are clinician-recorded, not independently clinically verified.

To delete a consultation, open it and select **Delete consultation**, acknowledge the confirmation and choose **Delete permanently**. The patient owner can delete their consultation, all versions of its notes, and associated follow-ups. Original uploaded documents remain in the vault. A metadata-only deletion audit event remains. Doctors and administrators cannot delete consultations. There is no entered-in-error/restoration workflow.

Doctors request clinical viewing and optional creation/correction permission in the access-request form. The patient sees these permissions before approval and can revoke them. Clinical sharing includes all consultation/follow-up history and requires all document categories without selected-record restrictions so source documents remain accessible. Document-upload permission is separate. Administrators have no clinical access.

The authenticated `/api/v1/clinical` API provides encounter and follow-up create/list/detail/correction/history routes and a paginated timeline. Corrections use `expected_version` and `correction_reason`; `DELETE /encounters/{id}?expected_version=N` requires the current version. Conflicting edits/deletion return HTTP 409. See the API docs and [milestone design](docs/CLINICAL_RECORDS.md). These tasks do not send reminders, book appointments or estimate clinical risk.

## Medication use and reconciliation

The dashboard also includes **Medication use & reconciliation**. Patients can report taking/not taking/being unsure about a medicine, leave unknown dose/frequency empty and optionally link a historical prescription. Only patients can correct their accounts. Verified doctors with clinical write consent can compare the account and source, record a discrepancy or clarification, and retain a separate reconciliation history. Later report/source changes flag the review as stale. See [medication-use workflow](docs/MEDICATION_USE.md).

## Document processing

New uploads are queued for the local background worker. Open **Show processing** on a document card to see progress, failures, unverified source text and per-page OCR details. The Docker worker includes Tesseract/Poppler and reads printed images/scanned PDFs locally. Missing tools, unreadable pages and processing limits are explicit. English printed text is the initial integration target; handwriting and OCR confidence are not clinically validated. Original uploads remain unchanged.

Select **Review transcription** to correct the text, record a reason and acknowledge checking the original patient/date association. Saved reviews retain original generated text, author and previous versions. Patient reviews remain distinct from clinician reviews, and neither automatically verifies diagnoses, doses or medication safety. Doctors need source access plus explicit clinical viewing/writing consent. Owners can select **Run updated OCR** for older processing results within the attempt limit; earlier reviews retain their processing snapshot.

Docker Compose includes the worker. For host development, run `.venv/Scripts/python.exe -m app.worker` from `backend`; install Tesseract/Poppler and configure their commands to enable host OCR. See [processing architecture and commands](docs/DOCUMENT_PROCESSING.md). Storage defaults to local files. The optional S3/MinIO configuration is documented there and preserves old local-document links.

For prescription documents, save a transcription review, then choose **Generate prescription draft**. Explicitly labelled medication lines produce uncertain candidates; unsupported layouts need manual source passages. Every supplied field must match exact source text. Patients can save drafts; only a verified doctor with clinical write consent can confirm historical entries after checking the original and acknowledging missing details. Drafts and confirmed entries retain their sources and previous versions. These records do not establish current use or medication safety. See [prescription workflow and supported labels](docs/PRESCRIPTION_DRAFTS.md).

## Terminology and research completion

Prescription rows support exact-alias terminology proposals from a pinned approved offline catalog or clearly artificial fixtures. Associations require their own clinician review and retain original text, evidence, catalog hash/release and history. No matching, dose or safety result is guessed. See [medication terminology](docs/MEDICATION_TERMINOLOGY.md).

The **Registered synthetic intervention study** shows the executed offline study fixture separately from patient outcomes. The evaluator validates registration, assigned versus received treatment, pre-assignment features, outcome timing and missingness, and does not estimate clinical effects from observational counts. See [study tooling](docs/INTERVENTION_STUDIES.md).

Backend quality tooling is separately hash-locked. From the root, install `backend/requirements-dev.lock.txt` into the project environment, then run:

```powershell
backend/.venv/Scripts/python.exe -m ruff check backend/app backend/tests backend/migrations scripts research --config backend/pyproject.toml
backend/.venv/Scripts/python.exe -m ruff format --check backend/app backend/tests backend/migrations scripts research --config backend/pyproject.toml
```

Biome replaces the legacy lint dependency graph; Node 22 LTS is used in containers. See [quality and privacy-safe logging](docs/QUALITY_CHECKS.md). The browser suite includes automated accessibility/keyboard checks and a bounded synthetic concurrent-read smoke. These do not establish independent accessibility certification or production capacity. CI also defines container builds and a verified source-only artifact after the test jobs; it has not been pushed or run remotely.

## Docker development setup

Prerequisites: Docker Desktop. Generate configuration with Python 3.12 (this workspace also has a restored `backend/.venv/Scripts/python.exe`):

```powershell
backend/.venv/Scripts/python.exe scripts/configure.py
docker compose up --build -d
```

On a fresh checkout, use an installed Python 3.12 interpreter to run `scripts/configure.py`, or create root `.env` from `.env.example` with independent random, URL-safe secrets. The configuration script never overwrites existing files or prints secrets.

- Application: http://localhost:3300
- API documentation: http://localhost:8001/docs
- Backend readiness: http://localhost:8001/ready
- PostgreSQL: `127.0.0.1:55432`

Ports are configurable through `FRONTEND_PORT`, `BACKEND_PORT` and `POSTGRES_PORT` in root `.env`. These defaults avoid the older development servers already present in this workspace. PostgreSQL and uploaded documents persist in Docker volumes. Startup applies migrations; successful readiness is required before starting the frontend.

There are no default production credentials. Create a patient or doctor through registration. Provision an administrator explicitly:

```powershell
docker compose exec backend python -m app.cli create-admin --email admin@example.com --name "Platform Administrator"
```

The command asks for a password without displaying it. A doctor remains pending until an administrator records a verification decision and evidence reference. A recorded administrator decision is not a live medical-license registry integration.

## Local development without Docker

With Python 3.12 and Node.js 22 installed:

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install --require-hashes -r backend/requirements.lock.txt
backend/.venv/Scripts/python.exe scripts/configure.py
cd backend
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000 --no-access-log
```

In another terminal:

```powershell
cd frontend
npm ci
npm run dev
```

Open http://localhost:3000. Browser API calls use the same-origin `/api/v1` proxy. `API_PROXY_TARGET` configures its backend target (default `http://127.0.0.1:8000`). Public browser environment variables are not used for internal Docker hostnames.

**Existing database:** the original workspace SQLite database has not been modified. If local startup reports an existing unversioned schema, stop the old backend and run `backend/.venv/Scripts/python.exe scripts/adopt_legacy_sqlite.py` from the repository root. This checks for the original six-table column layout, backs it up and migrates it. It refuses unknown layouts. Review the [operations guide](docs/OPERATIONS.md) first; never delete an existing database to make startup pass.

## Verification

```powershell
cd backend
.venv/Scripts/python.exe -m pytest -q
cd ../frontend
npm run lint
npm run typecheck
npm run format:check
npm run build
npm exec playwright install chromium
npm run test:e2e
```

Browser tests create disposable synthetic databases, documents and test-only users on ports 3100/8100. On Windows, process permissions must allow starting/stopping Chromium and its server process trees. They do not use the workspace database or Docker application users.

With the Compose PostgreSQL service running, from the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/check_postgres.py
```

This creates a uniquely named temporary PostgreSQL database, checks migrations against model metadata, runs the API suite and drops only that generated test database. `CAREGAP_POSTGRES_URL` can supply a dedicated test server instead. Tests must never target real clinical data.

Build artifacts for the browser suite use `.next-e2e`; the regular app uses `.next`. Set `NEXT_DIST_DIR=.next-build` for an isolated production build while another development server is running.

API contracts are available in FastAPI's `/docs` and `/openapi.json`. Authorization checks are centralized in `backend/app/services/authorization.py`. See [operations and remaining deployment requirements](docs/OPERATIONS.md).
