# Development operations and deployment boundaries

## Configuration and startup

Root `.env` supplies Docker secrets/ports; `backend/.env` supplies the host-run API. They are separate configurations and are ignored by Git and container contexts. `scripts/configure.py` generates random keys without overwriting existing configuration. Known example keys are rejected. `ENVIRONMENT=production` additionally requires secure cookies; TLS and appropriate proxy/origin configuration must be supplied before any deployment.

Compose is a local development configuration. Its services bind to loopback. PostgreSQL and documents persist in named volumes. Stop services with `docker compose stop`; this preserves data. Do not remove volumes to solve a migration error.

`/health` is liveness. `/ready` checks that the migration-version table is reachable. Container startup first executes `alembic upgrade head`; readiness is not a clinical or security certification.

## Existing SQLite data

The original `backend/caregap360.db` is preserved. The original `backend/venv` is also preserved; use `backend/.venv` for the restored runtime.

For the exact original unversioned six-table layout, stop the old backend and run:

```powershell
backend/.venv/Scripts/python.exe scripts/adopt_legacy_sqlite.py
```

The tool checks table/column names, creates a SQLite backup under ignored `backend/storage/backups`, stamps the known baseline, then applies new revisions. It does not certify arbitrary existing constraints or data quality. Unknown schemas are rejected for manual review. Existing grants become read-only unless separately approved for uploads. Old tokens are invalid because current authentication requires a database session.

Backups are sensitive data. Local development backups are not application-encrypted. Use approved encrypted storage, restricted access and retention controls before handling real medical information.

## Backup and recovery plan

For a future environment handling sensitive records, a consistent backup includes PostgreSQL, the private document store, schema version and recoverable encryption/key-management configuration. Quiesce writes or use an explicitly coordinated database/object-storage snapshot. Test restoration into an isolated environment, verify document checksums and authorization, and measure actual recovery objectives. A database dump alone does not restore uploaded files.

This repository does not claim an executed production restore drill. Do not run a restore over an active database without an approved recovery procedure.

## Security boundaries

- Administrators provisioned through the CLI can manage verification/operational metadata, not browse clinical documents.
- Doctor professional verification records an administrator's evidence review. Hospital affiliation is currently self-reported; no license-registry, organization membership or ABDM verification is implied.
- Grants control document category, optional selected IDs, duration and upload action. Revocation blocks subsequent API requests, not existing authorized downloads.
- Files are not served from a public static directory. API downloads authenticate, authorize and check the upload checksum. Application-level encryption, malware scanning, immutable object storage and hardened document sandboxing remain future controls.
- Audit events are database rows, not tamper-resistant immutable storage. Access history is available to patients; admin responses omit clinical details.
- Browser sessions use HttpOnly/SameSite cookies, origin checks and server-side revocation. API clients may use the returned bearer token. Never place tokens in URLs or application logs.
- Throttling currently uses process-local memory. Shared rate-limit storage and trusted-proxy configuration are required before multi-worker deployment.
- Tenant/organization isolation, retention/deletion, patient identity proofing, correction/version history and independent privacy/security review remain open requirements.

## Verification and CI

Backend fixtures use in-memory SQLite by default and a temporary directory patched into the actual storage service. They never run application table creation on the configured workspace database. `scripts/check_postgres.py` creates/drops a unique synthetic database and runs migrations plus the same API suite. Browser tests use a separate disposable SQLite database and synthetic administrator. Neither test path uses real patient records.

The GitHub Actions workflow defines SQLite/PostgreSQL, frontend lint/types/build and browser checks. It has been added locally; no remote workflow run or deployment has been performed.

For this workstation's throttled package network, a complete Linux wheel cache was prepared under ignored `backend/wheelhouse`. Every artifact was fetched from official PyPI and its SHA-256 checked against `requirements.lock.txt`. Docker uses this cache offline when wheels are present; a clean checkout downloads locked packages normally. Do not add an incomplete or untrusted wheel cache. Package hashes remain mandatory in either path.
