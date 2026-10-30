# CareGap 360

Patient-controlled medical documents and care-continuity foundations. This development release implements the first vertical slice from the master prompt plus a patient consent and professional verification workflow. Use synthetic data only until the required clinical, privacy, security and operational reviews are completed.

## Working functionality

- Patient and pending-doctor registration; bcrypt passwords; expiring JWT sessions with server-side revocation.
- Browser authentication using HttpOnly, SameSite cookies. Credentials are not stored in localStorage.
- Patient profile viewing/editing, including date of birth and clearing optional fields.
- PDF/JPG/PNG uploads with actual content validation, size limits, source metadata and SHA-256 checks on download.
- Patient-owned record library with search, category filters, authenticated downloads and explicit unverified status.
- Verified doctor access requests with purpose, duration, document category and optional upload permission.
- Simple patient sharing IDs such as `CG-48273184`, displayed on the patient dashboard and accepted in the doctor's access-request field. The field shows an example; existing UUIDs remain internal and continue to work through the API.
- Patient approval/denial, optional selected-document sharing, grant expiration and revocation.
- Doctor workspace listing only authorized patients and records; uploads only with explicit permission.
- Administrator professional verification queue and operational audit metadata. Administrators have no automatic clinical-record access, and public registration cannot create administrators.
- Patient-visible audit history, bounded requests, authentication throttling and deny-by-default authorization.
- Alembic migrations, isolated backend tests, PostgreSQL regression checks, Playwright browser tests and a CI workflow.

OCR/extraction, structured clinical encounters and medication records, reconciliation, predictive models, intervention evaluation, messaging, FHIR/ABDM and organization isolation are not implemented. Local storage is not application-encrypted or an S3 integration. See [progress](docs/PROGRESS.md), [architecture](docs/ARCHITECTURE.md) and [roadmap](docs/ROADMAP.md).

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
.venv/Scripts/python.exe -m uvicorn app.main:app --reload --port 8000
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
