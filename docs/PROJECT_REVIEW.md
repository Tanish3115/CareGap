# CareGap 360: master prompt review

Review date: 30 October 2026. Scope: repository source, configuration, supplied master prompt, and available local checks. This is an engineering review, not a clinical or compliance certification. No existing patient records were read.

## Verdict

The stack and directory structure are a reasonable starting point for the requested modular monolith. The implementation is an early patient document-vault slice, with partial foundations for doctor consent. It does not yet satisfy Phase 1 or Phase 2 acceptance in a reproducible environment, and does not implement the advanced platform described in the prompt. Critical authorization issues must be addressed before using real health information.

## Prioritized findings

Findings below are established from source inspection unless explicitly described as a completed runtime check.

| Priority | Finding and evidence | Required correction |
| --- | --- | --- |
| Critical | Public registration accepts `admin` (`backend/app/schemas/auth.py:9`); registration persists the supplied role (`backend/app/api/auth.py`). Admins can list every patient's documents and bypass document access checks (`backend/app/api/documents.py:33`, admin list branch). An unauthenticated caller can therefore register an account with broad health-record access. | Remove admin from public registration; provision administrative identities through a controlled workflow. Remove implicit clinical access from the administrator role. Add regression tests covering list, metadata, download, and upload. |
| Critical | A known default JWT signing key is accepted without a startup guard (`backend/app/config.py:12`); Compose also sets it. When that key is used, someone who knows an existing user ID can sign a token impersonating that user. Authentication rechecks the database user, but cannot distinguish that forged signature. | Require a securely configured signing key outside an explicitly local development mode, and rotate exposed keys and sessions before deployment. |
| High | Doctor/admin uploads accept a supplied patient ID without consent, doctor verification, or an explicit patient-existence check (`backend/app/api/documents.py:106`). | Authorize the target patient before writing a file; specify separate read and write permissions and deny by default. |
| High | Doctor reads check grants but never require `verification_status == verified`. Unknown grant scopes fall through to broad access, and only the first active grant is considered (`backend/app/api/documents.py:46`, `:61`, `:208`). | Centralize authorization; validate scope values, reject unknown values, and evaluate the union of valid grants without admitting unverified doctors. |
| High | Upload validation trusts the filename and client MIME header. Arbitrary bytes and empty files can be stored as PDF/images. String-prefix path checks accept sibling paths with the same prefix (`backend/app/services/storage_service.py:45`, `:78`). Upload patient IDs are unrestricted strings. | Validate actual file content, extension/MIME agreement, nonempty content and parseability; enforce path ancestry and canonical patient identifiers. Add adversarial tests. |
| High | Storage hashes files on upload but does not verify those hashes on retrieval. Files are ordinary filesystem writes; application encryption, object immutability and tamper-resistant audit storage are absent. Upload UI nevertheless says files are encrypted. | Remove unsupported claims; design encryption/key management and storage integrity controls. SHA-256 alone provides neither encryption nor non-repudiation. |
| High | No patient access-request, approval, grant, revocation, or audit-history API/UI exists. Tests insert consent rows directly into the database. | Implement the patient-controlled workflow and test it through public endpoints. A consent table is not a working consent product. |
| High | Docker PostgreSQL URL requires the default `psycopg2` driver, which is absent from `backend/requirements.txt`. Frontend Dockerfile copies a nonexistent `public` directory. | Add a matching PostgreSQL driver and resolve the absent build directory; verify a fresh Compose startup. |
| High | Client API URL is compiled from `NEXT_PUBLIC_API_URL`; Compose supplies it only at runtime and points it at the Docker-only hostname `backend`. The compiled fallback points to browser loopback. Neither is a reliable deployed browser API topology. | Select a same-origin proxy or pass a browser-reachable API URL at build time. Check API path rewriting to avoid duplicating `/api/v1`. |
| High | There are no `.dockerignore` files. Backend `COPY . .` can include the local database, uploaded documents, virtualenv and local environment files in the build context/image. Frontend similarly copies local build/dependency artifacts. | Exclude secrets, clinical files, databases, environments, dependencies and build output before building images. |
| Medium | Test storage fixture changes settings after the singleton storage service has already been initialized (`backend/tests/conftest.py:38`). TestClient also invokes application startup against the global engine, not the overridden session. Test engine does not enable SQLite foreign keys. | Patch/inject the storage service itself, isolate startup and database engine, and enforce foreign keys. Do not run the present tests against a workspace holding clinical data. |
| Medium | Audit rows are normal mutable database rows. List reads, patient profile reads/changes and some rejected requests are not audited. Audit writes commit independently after clinical mutations. | Define complete audit coverage, redact unnecessary sensitive details, and make successful mutations and their audit events transactional; use stronger retention controls when required. |
| Medium | `active_doctor_grants` counts expired/revoked grants; care gaps are hardcoded to zero (`backend/app/api/patients.py:105`). Dashboard request failures can become fabricated zero metrics. | Query only effective grants; represent unavailable analytics and failed loads explicitly. |
| Medium | Dashboard sends doctors to document listing without the required patient ID (`frontend/src/app/dashboard/page.tsx:88`). Doctor/admin dashboards are not implemented. Identity and clinical-record verification labels are unconditional. | Add role-specific flows; display onboarding/verification state from evidence. Do not label uploaded records clinically verified. |
| Medium | Date of birth is accepted at registration but never persisted. Invalid clinical dates silently become null. Document type and title are insufficiently validated. | Use typed, bounded request schemas and explicit validation errors. |
| Medium | No Alembic configuration or migrations exist, despite listing Alembic as a dependency. Startup calls `create_all`, which cannot evolve existing schemas. | Add and verify baseline migrations and an explicit database upgrade procedure. |
| Medium | No rate limiting, server-side session revocation/refresh workflow, tenant/organization isolation, retention/deletion workflow, backup restoration proof, CI, frontend tests or E2E suite exists. JWTs live in localStorage. Password input is unbounded despite bcrypt's input limits. | Complete the security and operational foundation incrementally with targeted tests and a session threat model. |

## Requirements coverage

| Master prompt area | Status | Observed implementation or gap |
| --- | --- | --- |
| Phase 1 foundation | Partial | Next.js/FastAPI scaffold, patient/doctor registration, bcrypt/JWT, models and tests; startup reproducibility, role isolation, migrations, CI and role-aware dashboards incomplete. |
| A: unified records / Phase 2 | Partial | Patient profile API, upload/list/metadata/download, local files and basic provenance. No encounters, clinical timeline, diagnoses, allergies, labs as structured results, referrals or record versioning. |
| B: prescription digitization / Phase 3 | Unimplemented | Status enum exists; no OCR, extraction, queue, normalization, uncertainty handling or review workflow. |
| C: consent / Phase 4 | Partial | Grant model and some read checks. No operational patient-controlled sharing workflow, identity verification administration or record-level grants. |
| D/E: medication intelligence / Phase 5 | Unimplemented | No medication or reconciliation models, comparison workspace, knowledge-provider interface or evidence-based safety alerts. |
| F: risk analytics / Phase 6 | Unimplemented | No outcome data, training pipeline, model, calibration, subgroup evaluation or explanations. |
| G: interventions / Phase 7 | Unimplemented | No intervention event schema, suggestions, outcomes or causal evaluation plan. |
| H: dashboards | Partial | Patient document UI with loading/error/empty states, search and type filters. Doctor/admin workflows absent. |
| I: grounded summary / Phase 8 | Unimplemented | No authorized retrieval or source-cited summary pipeline. |
| J: coordination / Phase 8 | Unimplemented | No appointment/test/referral tasks, scheduling, notification preferences or mock providers. |
| Interoperability / Phase 8 | Unimplemented | An ABHA ID field is present; no FHIR adapters, conformance tests or ABDM integration. |
| Hardening / Phase 9 | Partial | Some backend authorization tests and Dockerfiles. No reproducible full-stack validation, staging, deployment pipeline or recovery exercises. |

## Verification

- Passed: `frontend/node_modules/.bin/tsc.cmd --noEmit --incremental false`.
- Passed: `npm run build` in `frontend` (Next.js 14.2.35); all application routes compiled and prerendered. Webpack emitted cache snapshot warnings, but the command exited successfully. This does not verify API connectivity or browser workflows.
- Backend test execution blocked: `backend/venv/Scripts/python.exe` references a missing Python 3.10 installation. `python` is not on PATH and `py` reports no installed interpreters. Fifteen test functions exist, but none were executed successfully during this review.
- Existing tests cover basic patient/doctor registration, login, patient ownership, absent/active/revoked doctor consent, a disallowed extension and upload/download. They do not prove token expiration, doctor verification, scope expiry, admin isolation, upload consent, content integrity or the clinical uncertainty cases required by the prompt.
- Docker end-to-end startup and browser workflows were not verified. Static configuration findings above are independent of that limitation.
- No `.git` directory exists at the workspace root; establish source control before substantial implementation/refactoring.

See [ARCHITECTURE.md](ARCHITECTURE.md) for the current design and [ROADMAP.md](ROADMAP.md) for dependency-ordered acceptance criteria.
