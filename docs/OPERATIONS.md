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

The tool checks a fixed baseline of table/column names, creates a SQLite backup under ignored `backend/storage/backups`, stamps the known baseline, then applies new revisions. It does not certify arbitrary existing constraints or data quality. Unknown schemas are rejected for manual review. Existing grants become document read-only unless separately approved for uploads; migration `0005` leaves clinical viewing/writing disabled on existing grants and requests. Old tokens are invalid because current authentication requires a database session.

Backups are sensitive data. Local development backups are not application-encrypted. Use approved encrypted storage, restricted access and retention controls before handling real medical information.

## Backup and recovery plan

For a future environment handling sensitive records, a consistent backup includes PostgreSQL, the private document store, schema version and recoverable encryption/key-management configuration. Quiesce writes or use an explicitly coordinated database/object-storage snapshot. Test restoration into an isolated environment, verify document checksums and authorization, and measure actual recovery objectives. A database dump alone does not restore uploaded files.

This repository does not claim an executed production restore drill. Do not run a restore over an active database without an approved recovery procedure.

## Security boundaries

- Administrators provisioned through the CLI can manage verification/operational metadata, not browse clinical documents.
- Doctor professional verification records an administrator's evidence review. Hospital affiliation is currently self-reported; no license-registry, organization membership or ABDM verification is implied.
- Grants control document category, optional selected IDs, duration and upload action. Revocation blocks subsequent API requests, not existing authorized downloads.
- Consultation/follow-up viewing and writing require separate explicit clinical permissions. Clinical sharing includes historical revisions and requires all document categories without selected-record restrictions. Corrections append attributed revisions, use expected-version checks, and preserve prior source links. These are application-level histories, not database- or administrator-proof immutable records.
- Patients can permanently delete their own consultation, note revisions and dependent follow-up histories after confirmation. Doctors/admins cannot delete consultations. Original uploads and a metadata-only audit event remain. Backups retain their own data until their retention policy removes it; this feature is not complete privacy erasure. The previous entered-in-error controls/routes/filters were removed; legacy schema compatibility is retained.
- Migration `0007` adds the durable processing queue without automatically processing existing files. New uploads enqueue transactionally. Compose starts a separate worker; host development needs `.venv/Scripts/python.exe -m app.worker` from `backend`. Worker restarts recover expired leases; attempts are capped at three. Owners can request/retry through the document panel. Results are unverified, and raw parser exceptions/source text are excluded from logs.
- Migration `0008` defaults old uploads to local storage and adds source-review history. New S3 routing is optional; never move/delete old files to enable it. Remote materialization is bounded and checksummed before downloads or processing. Use private buckets, scoped app credentials and HTTPS for production custom S3 endpoints, including when new uploads remain local but old S3 documents are still served.
- Docker includes local English Tesseract/Poppler. OCR limits and low-confidence words are visible; unreadable content remains unverified. Transcription reviews require original-source/patient/date confirmation and clinical consent for doctors; they do not verify prescribing or clinical safety. Review history snapshots the original processing attempt and is retained when owners update older OCR results.
- Files are not served from a public static directory. API downloads authenticate, authorize and check the upload checksum. Application-level encryption, malware scanning, immutable object storage and hardened document sandboxing remain future controls.
- Audit events are database rows, not tamper-resistant immutable storage. Access history is available to patients; admin responses omit clinical details.
- Browser sessions use HttpOnly/SameSite cookies, origin checks and server-side revocation. API clients may use the returned bearer token. Never place tokens in URLs or application logs.
- Development throttling defaults to process-local memory. `RATE_LIMIT_STORAGE_URI` supports shared Redis; production rejects memory/plaintext Redis and requires `rediss://`. Configure authenticated TLS Redis and trusted proxies before real multi-worker deployment. URI credentials are secret settings and must not be logged.
- Organization-bound grants recheck verified membership and are revoked when organization/membership access is removed. Membership alone gives no clinical access. Nine clinical groups with patient narrowing are implemented. Identity proofing, provider/backup retention procedures, tamper-resistant history and independent privacy/security review remain open requirements.

## Approved offline erasure

See [PRIVACY_ERASURE.md](PRIVACY_ERASURE.md) for the explicit plan/review/execute CLI, eligibility checks, maintenance requirements, retained metadata, recovery and backup/provider limits. Planning does not delete data. The operator was verified on disposable synthetic accounts; no current application records were erased. Administrative request closure alone never invokes it.

## Backup, restore and isolated demos

From the repository root:

```powershell
backend/.venv/Scripts/python.exe scripts/backup_local.py
backend/.venv/Scripts/python.exe scripts/check_restore.py
backend/.venv/Scripts/python.exe scripts/seed_synthetic.py
```

Backups go to new ignored `.tools/backups/<timestamp>-<random>` folders and include a PostgreSQL dump, local vault archive and SHA-256 manifest. Existing backups are not overwritten. S3 objects require a separate provider snapshot; the manifest reports their count. Credentials/keys are deliberately not copied and need a separate approved escrow/recovery process.

The restore exercise creates two generated synthetic databases, migrates the source, dumps/restores it, checks schema/data/checksums and drops only those generated databases after closing connections. It never restores over application data. The executed fixture validates the recovery path, not a production recovery-time objective or every object-store failure scenario.

Synthetic seeding creates a separate `.tools/demo/<random>/demo.db`, private fixture vault, `demo.env` and random credentials file. It never seeds/replaces the normal application database. Credentials are not printed. For a separate backend, use Uvicorn's `--env-file <absolute demo.env>` option on another port, with the same environment for its worker; do not overwrite normal `.env` files. Fixtures are explicitly synthetic and document processing remains an actual queued task.

## Local HTTPS/shared-Redis rehearsal

```powershell
backend/.venv/Scripts/python.exe scripts/configure_staging.py
docker compose build
docker compose -f docker-compose.yml -f infra/staging/compose.yml --env-file .tools/staging.env up -d --no-build --wait
backend/.venv/Scripts/python.exe scripts/check_staging.py
```

This is a separate `caregap-staging` project with independent PostgreSQL/vault volumes and loopback-only HTTPS at `https://localhost:3443`. Caddy uses its local CA; the smoke client explicitly trusts a copied public CA file without modifying Windows/browser trust. It verifies certificates, Secure/HttpOnly sessions, record write/read, cross-patient denial, logout revocation and shared Redis counters using only new synthetic staging users. The client uses IPv4 TCP with localhost TLS/SNI to avoid the measured Windows IPv6 fallback delay. The normal application remains at `http://localhost:3300`.

The rehearsal deliberately uses development mode/private-network Redis and is not an approved production environment. Production requires managed PostgreSQL transport, encrypted database/volumes/backups, authenticated TLS Redis, key management and independent reviews. `LOCAL_VOLUME_ENCRYPTION_VERIFIED=true` asserts external verification; it does not encrypt anything. `S3_SERVER_SIDE_ENCRYPTION=AES256` or `aws:kms` configures new uploads; KMS requires `S3_KMS_KEY_ID`. Inventory/migrate older objects separately. Read DEPLOYMENT_GATES.md before deployment.

## Verification and CI

Backend fixtures use in-memory SQLite by default and a temporary directory patched into the actual storage service. They never run application table creation on the configured workspace database. `scripts/check_postgres.py` creates/drops a unique synthetic database and runs migrations plus the same API suite. Browser tests use a separate disposable SQLite database and synthetic administrator. Neither test path uses real patient records.

The GitHub Actions workflow defines SQLite/PostgreSQL, frontend lint/types/build and browser checks. It has been added locally; no remote workflow run or deployment has been performed.

For this workstation's throttled package network, a complete Linux wheel cache was prepared under ignored `backend/wheelhouse`. Every artifact was fetched from official PyPI and its SHA-256 checked against `requirements.lock.txt`. Docker uses this cache offline when wheels are present; a clean checkout downloads locked packages normally. Do not add an incomplete or untrusted wheel cache. Package hashes remain mandatory in either path.
