# CareGap 360

**CareGap 360** is an early implementation of a patient-controlled health-record platform. Current code provides registration/login, patient profile endpoints, and a document upload/list/download workflow. Medication intelligence, predictive care continuity, operational consent management and interoperability are planned capabilities.

**Review status (30 October 2026):** Critical authorization defects remain. This repository is not ready for real patient data or deployment. See the [master prompt comparison and prioritized findings](docs/PROJECT_REVIEW.md), [implementation-grounded architecture](docs/ARCHITECTURE.md), and [roadmap and progress](docs/ROADMAP.md).

---

## Architecture Overview

CareGap 360 starts with a modular monolith structure. FHIR mappings and the full healthcare authorization model are not implemented:

- **Frontend**: Next.js 14 (App Router), TypeScript, Tailwind CSS, Lucide icons, responsive accessible healthcare UI.
- **Backend**: FastAPI, Pydantic v2, SQLAlchemy 2.0, JWT authentication with bcrypt password hashing.
- **Data Persistence**: PostgreSQL (production/Docker) & SQLite (zero-friction local development & automated test isolation).
- **Document storage**: Local filesystem persistence with an upload SHA-256 checksum. Retrieval integrity verification, application encryption and private object storage are not implemented.
- **Consent foundation**: A time-limited, document-type-scoped `ConsentGrant` model and partial read checks. Patient approval/revocation APIs and UI are absent; authorization defects are documented in the review.
- **Audit service**: Database audit rows for selected actions. Complete coverage and tamper-resistant storage are not implemented.

---

## Directory Structure

```
CareGap/
├── README.md                 # Project documentation & execution guide
├── docker-compose.yml        # Multi-container orchestration (PostgreSQL, Backend, Frontend)
├── .env.example              # Environment variables template
├── .gitignore                # Source control ignore rules
├── backend/                  # FastAPI backend service
│   ├── requirements.txt      # Python dependencies
│   ├── Dockerfile            # Container build spec
│   ├── app/
│   │   ├── main.py           # Application entrypoint & CORS setup
│   │   ├── config.py         # Application settings
│   │   ├── database.py       # SQLAlchemy engine & session maker
│   │   ├── models/           # User, Patient, Doctor, Document, Consent, Audit models
│   │   ├── schemas/          # Pydantic v2 validation schemas
│   │   ├── api/              # Auth, Documents, and Patients endpoints
│   │   ├── services/         # Storage and Audit services
│   │   └── core/             # Security (bcrypt, JWT) and error definitions
│   ├── storage/documents/    # Secure document vault
│   └── tests/                # Automated pytest suite (Unit, Integration & Security)
└── frontend/                 # Next.js 14 frontend service
    ├── package.json          # Node dependencies
    ├── Dockerfile            # Multi-stage production container
    └── src/
        ├── app/              # Next.js App Router (Landing, Login, Register, Dashboard)
        ├── components/       # Navbar, DocumentCard, StatsCard, DocumentUploadModal
        ├── lib/              # API client, Auth session manager, Utilities
        └── types/            # TypeScript domain interfaces
```

---

## Getting Started

These are intended setup commands, not a currently verified clean-install procedure. The checked-in workspace's existing `backend/venv` points to a missing Python installation and must be recreated with a working interpreter. Docker setup also has unresolved driver/build/API-address issues listed in the review. Use synthetic data only.

### Option A: Local Development (Quickstart)

#### 1. Backend Setup
```bash
# From repository root
cd backend
python -m venv venv

# Windows PowerShell:
.\venv\Scripts\Activate.ps1
# Linux/macOS:
# source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
The FastAPI interactive documentation is accessible at: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

#### 2. Frontend Setup
```bash
# In a separate terminal, from repository root
cd frontend
npm install
npm run dev
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

### Option B: Docker Compose

Ensure Docker Desktop is running, then run:

```bash
docker compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)
- Interactive API Docs: [http://localhost:8000/docs](http://localhost:8000/docs)
- PostgreSQL Database: `localhost:5432`

---

## Automated Testing & Security Verification

The repository contains 15 backend test functions covering:
- Patient and clinician registration & authentication.
- Login with correct/incorrect credentials and authenticated profile retrieval.
- Basic PDF upload/download, checksum presence and rejection of a disallowed extension.
- Cross-patient unauthorized access rejection (HTTP 403 Forbidden).
- Zero-trust clinician consent verification (access denied without active patient grant).
- Consent revocation blocking future access.

After correcting test engine/storage isolation described in the review, run the test suite in a synthetic-only environment:
```bash
cd backend
$env:PYTHONPATH="."
.\venv\Scripts\pytest tests -v
```

The test session uses an in-memory database, but startup still touches the configured application engine and the storage fixture does not redirect the initialized storage singleton. Backend tests could not run during the 30 October 2026 review because the virtual environment references a missing interpreter. Frontend TypeScript checking and the production build passed (the build emitted cache snapshot warnings). Do not interpret the existence of tests as proof of clinical safety, production readiness or complete authorization coverage.

