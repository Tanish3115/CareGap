# Hosting preparation — 2 November 2026

Prepared locally for **Vercel (Next.js) + Render (FastAPI, OCR worker and cleanup worker) + Supabase (PostgreSQL and private object storage)**. Production configuration additionally requires **Upstash Redis or another TLS Redis service** for shared rate limiting.

This session does not deploy, publish source, create accounts, or transfer patient records. The existing published `deploy/free-demo` branch is an older, disposable demonstration profile. Its root `render.yaml` must not be used for persistent hosting. The new hosting files remain local until a reviewed publication step.

## Prepared artifacts

- `infra/hosting/render.yaml`: persistent backend blueprint; Docker context `backend`, command `python -m app.hosted`, readiness endpoint `/ready`, automatic deploys disabled. Runs migrations and supervises API/OCR/cleanup together; does not reset records or session keys.
- `frontend/vercel.json`: frontend build settings. Select repository root directory **frontend** in Vercel.
- `infra/hosting/*.env.example`: provider-specific templates without real credentials.
- `scripts/prepare_hosting.py`: creates ignored private environment files, a random session secret and application-table Data API lockdown SQL. It never connects to cloud services.
- `scripts/hosting_preflight.py`: offline configuration validation; never claims connection, private-bucket or external-review verification.
- `scripts/hosting_inventory.py`: read-only database counts, schema revision and document checksums; private output only under `.tools`.

The private preparation directory is `.tools/hosting/20261102T171812Z/`. Its `render.env` contains a generated secret; do not paste or commit it. Provider credentials and real hostnames remain blank/placeholders. Keep this directory private: Windows access permissions are inherited from the local account/workspace, not guaranteed by Python's Unix permission mode.

The private recovery backup is `.tools/backups/20261102T172123Z-97e0163c/`, containing a database dump, local vault archive and SHA-256 manifest. The read-only source inventory confirms schema **0019**, **3 documents**, all local document hashes verified, **0 active processing jobs** and **0 pending file cleanups**. It contains identifiers and storage keys and must remain private. This is a preparation snapshot; repeat it with writes stopped for the actual cutover. Existing records were not changed.

## Information needed next session

Create/sign in to free provider accounts and select compatible regions. Collect the Vercel project URL, Render service URL, Supabase project reference/region, PostgreSQL password and connection endpoint, generated S3 Access Key/Secret, private bucket name, and a TLS Redis URL. Enter secrets only in provider environment settings or the private local environment file. No paid domain is needed; provider subdomains suffice. Check current free-plan eligibility and limits before accepting service creation.

Vercel gets **only** `API_PROXY_TARGET=https://<backend>.onrender.com`. Set it before the production build because Next.js generates the API rewrite at build time. Keep the existing same-origin `/api` proxy and HTTP-only session flow. Set backend `CORS_ORIGINS` to a JSON array containing the exact HTTPS frontend origin. Do not expose database, Redis, storage or session keys through `NEXT_PUBLIC_*`. Supabase Auth is not used: CareGap's existing accounts/password hashes and sessions remain backend-managed.

Supabase database URI must use `postgresql+psycopg://` with `sslmode=require` (or certificate-verified TLS). Use the direct connection when reachable or the **session pooler on port 5432**, not the transaction pooler on 6543. URL-encode passwords. Start with one Render instance and review the connection budget for its three processes.

Create a **private** `caregap-private` bucket. Use generated server-side S3 credentials, never an anon key or service-role JWT as S3 credentials. These keys bypass RLS; retain them only on the backend. The S3 endpoint is `https://<project-ref>.storage.supabase.co/storage/v1/s3`; use the actual project region. Review upload limits, allowed MIME types and private anonymous-access rejection against the application upload policy.

Supabase uses managed encryption and does not accept AWS SSE headers. Leave `S3_SERVER_SIDE_ENCRYPTION` empty. Keep `S3_MANAGED_ENCRYPTION_VERIFIED=false` until the operator reviews the target service's encryption and private-storage setup and records a meaningful `S3_ENCRYPTION_REVIEW_REFERENCE`. This flag records an external review; it does not perform encryption verification or clinical certification. Generic S3 production profiles still require their encryption configuration.

## Cutover order for the next prompt

1. Review the local source changes and source-only archive. Publish only the reviewed deployment source when authorized; do not publish `.tools`, environments, backups or patient files. The existing remote demo branch does not contain these new preparations.
2. Provision a dedicated Supabase target, private bucket and TLS Redis service. Keep the API private/unpublished while preparing data. Fill the private Render environment and run the offline preflight below. Validate connectivity and actual bucket privacy separately.
3. Stop application writes and wait for OCR/cleanup to drain. Take a fresh consistent backup and compare counts/checksums with this inventory. Preserve the original local deployment and backup for rollback.
4. Restore **only CareGap application tables/data** into an empty dedicated target, preserving UUIDs, foreign keys and password hashes. Review the dump's table ownership, extension and grant statements first. Do not blindly restore a whole database or overwrite Supabase `auth`/`storage` schemas. The current dump is a recovery artifact, not a reviewed one-command Supabase import. Prepare and test the application-only restore against a disposable target before the real transfer.
5. Copy each source document to the private bucket using its existing storage key. The resumable command is now implemented; follow [STORAGE_MIGRATION.md](STORAGE_MIGRATION.md) to preview and then apply during maintenance. It validates patient namespace, size and SHA-256, uses conditional object creation, downloads to verify bytes and commits each storage pointer only after verification. Local copies remain. Global `STORAGE_BACKEND=s3` alone **does not migrate existing rows/files**. Verify the selected provider supports conditional writes and private access before executing; no cloud file transfer has occurred in this preparation session.
6. Run Alembic to head and review/apply the generated `supabase_public_schema_lockdown.sql` after migrations. It enables RLS and revokes `anon`/`authenticated` grants on registered application tables only. The backend must use the intended table-owner connection; verify it can still operate. Disable public Data API exposure if unused. Revisit lockdown after future migrations create tables.
7. Deploy the persistent Render blueprint, then Vercel with the correct build-time API target. Verify readiness, registration/login/logout, CSRF, access denial between patients, private upload/download/delete, OCR jobs and cleanup, consultations and multilingual navigation. Use synthetic accounts for acceptance checks, and confirm reboot survival, persistence and rollback before reopening writes.

Supabase S3 versioning is unsupported; deletions require a separate recovery plan. Free-service sleeping, resource limits and backup limitations also need acceptance before depending on the public service. External clinical/data approvals and independent production reviews remain separate gates; preparing hosting does not complete them.

## Local commands

From the repository root in PowerShell:

```powershell
# Creates a NEW private folder and NEW session secret; does not deploy.
backend/.venv/Scripts/python.exe scripts/prepare_hosting.py

# Use the generated folder's actual path. Exit 2 means missing/rejected configuration.
backend/.venv/Scripts/python.exe scripts/hosting_preflight.py --env .tools/hosting/20261102T171812Z/render.env

# Repeat immediately before a future cutover; keep private outputs local.
backend/.venv/Scripts/python.exe scripts/backup_local.py
backend/.venv/Scripts/python.exe scripts/hosting_inventory.py --output .tools/hosting/cutover-inventory.json
```

References: [Supabase S3 compatibility](https://supabase.com/docs/guides/storage/s3/compatibility), [S3 authentication](https://supabase.com/docs/guides/storage/s3/authentication), [database connections](https://supabase.com/docs/guides/database/connecting-to-postgres/pooling-and-limits), [Vercel monorepos](https://vercel.com/docs/monorepos), [Redis TLS](https://upstash.com/docs/redis/features/security).
