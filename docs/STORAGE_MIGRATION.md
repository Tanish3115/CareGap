# Private document storage migration

Implemented 7 November 2026. This is an operator command, separate from public APIs. It does not provision hosting, certify bucket privacy, migrate the database to another provider or remove local files.

Before a real transfer, approve the destination/privacy configuration, verify private bucket access and encryption, back up the database and vault, and stop all API writes, OCR and cleanup workers. Configure the existing backend database, local storage directory and S3 settings privately. Do not run against a different database by mistake.

From `backend`, preview with:

```powershell
.\.venv\Scripts\python.exe -m app.migrate_storage
```

Preview verifies local source hashes, sizes and patient namespaces without uploading or changing records. Already-remote records require authenticated downloads for integrity checking, so preview can read the configured remote store.

After reviewing the inventory and completing maintenance prerequisites:

```powershell
.\.venv\Scripts\python.exe -m app.migrate_storage --apply --writes-and-workers-stopped
```

Each local document is uploaded with atomic `If-None-Match: *`, then downloaded and independently checked against its stored SHA-256 and size. Only then is its database pointer committed. Original IDs, keys, clinical timestamps and local files are preserved. Existing matching objects support resume after an upload succeeded but the database transaction did not commit. Conflicting objects, unsupported conditional creation, invalid sources and provider failures stop the operation without switching that document. No unconditional overwrite fallback is used.

The command commits one document at a time. Earlier successful documents remain migrated if a later document fails. Retry after privately investigating the failure; already-migrated documents are reverified. A copied object can remain after rollback; preserve it for the verified retry. No cloud deletion or automatic rollback of committed pointers occurs. Keep the same bucket configuration throughout; pointers do not encode bucket identity.

The maintenance flag is an operator acknowledgement, not an automatic distributed write lock. Do not run multiple migration processes or resume application workers during transfer. Row locks protect PostgreSQL records; SQLite still requires exclusive operational maintenance. Recheck private source inventory, downloads, application authorization and restart persistence before reopening writes. Local-copy retention and later erasure require a separately reviewed policy.

Synthetic tests cover preview, clean transfer, matching/conflicting destinations, interruption before database commit, source corruption/size/namespace errors, failed downloads and providers rejecting conditional uploads. Actual provider compatibility, anonymous-access rejection and managed encryption must be checked against the selected service before transferring patient files.
