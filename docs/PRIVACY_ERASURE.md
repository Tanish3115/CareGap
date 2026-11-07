# Offline patient erasure operator

This tool removes an approved patient's current local record graph and private source files. It is deliberately separate from the HTTP API. Submitting or closing a privacy request does not run it. It has been exercised only against disposable synthetic data; no existing application account or source was erased during development.

The operator needs database and vault privileges, an active operational administrator, and an independently approved retention decision. A policy reference records that decision; the application cannot verify its legal or institutional approval. Stop the API, workers and filesystem writers before execution, keeping the database available. PostgreSQL execution also locks application tables with a five-second acquisition timeout. SQLite execution relies on exclusive offline maintenance.

## Eligibility and reviewed plan

Patient-facing record deletion is a separate workflow; see RECORD_DELETION.md. Migration `0019` adds its durable private-file cleanup queue. Finish pending file cleanup before planning account erasure. Completed receipts are included in the owned erasure graph; pending receipts cannot be discarded while their private objects remain.

Use the existing administrative workflow to deactivate the patient and revoke sessions. Revoke every consent grant, including expired grants, and resolve queued/processing jobs to terminal states with workers stopped. An erasure request must be `under_review`, with its decision reference matching the approved policy. The account must be patient-only and the approved eligibility date must have arrived.

Keep a private policy JSON outside source control, for example under ignored `.tools/erasure`. Replace the example references and date with the approved decision; do not use this sample as an approval:

```json
{
  "reference": "APPROVED-RETENTION-DECISION-REFERENCE",
  "backup_procedure_reference": "APPROVED-BACKUP-PROCEDURE-REFERENCE",
  "eligible_after": "2099-01-01T00:00:00Z",
  "retain_pseudonymous_account": true
}
```

From `backend`, with the intended database/vault environment configured, planning is read-only:

```powershell
.venv/Scripts/python.exe -m app.privacy_admin plan --request-id <REQUEST-UUID> --admin-id <ADMIN-UUID> --policy <PRIVATE-POLICY.json> --plan <NEW-PRIVATE-PLAN.json>
```

Review the exact patient/user UUIDs, policy, per-table counts, source objects and consequences in the private plan. The command prints its SHA-256 and aggregate counts; source content and credentials are omitted. Plans contain private identifiers and storage keys. Keep them under restricted operator access and approved retention; creation mode is not a Windows ACL or encryption guarantee.

## Execution and recovery

Only an authorized operator should run the following after reviewing the concrete plan and arranging the separate backup procedure:

```powershell
.venv/Scripts/python.exe -m app.privacy_admin execute --plan <REVIEWED-PRIVATE-PLAN.json> --expected-plan-sha256 <EXACT-PLAN-SHA256> --confirm-user-id <EXACT-USER-UUID> --maintenance-confirmed --receipt <NEW-PRIVATE-RECEIPT.json>
```

Execution rechecks the full database fingerprint and eligibility. Changed records, approvals or administrative history require a new review. Unknown dependent tables, cross-patient references, shared/aliased paths, linked files, malformed checksums and external storage fail closed. All remaining local files are hash-checked before the first deletion and checked again before removal. Any S3 object blocks this execution before local deletion; versioned objects, retention locks and remote snapshots need a provider-specific procedure.

File deletion and database transactions cannot be atomic together. A private progress journal records completed local removals. If a storage operation fails, database rows remain and the same reviewed plan can be retried in maintenance after resolving the fault. Existing files are always revalidated; the journal cannot bypass checks. Do not recreate deleted source files or edit affected database records during recovery. A failure after some removals leaves an intentionally incomplete operation that the operator must finish or recover through the approved procedure.

The receipt is committed in the audit transaction with database erasure. If writing its output file fails after commit, repeat the same exact execution command using an unused receipt path; it recovers the committed receipt without repeating deletion. Keep the plan/progress until the approved completion review. The CLI never overwrites an existing plan or receipt.

## Retained data and limits

The account becomes inactive and pseudonymous, with a new random password hash. Its clinical profile, source objects, owned clinical/revision/lineage data, sessions, grants and notification records are removed. Reactivation of the erased patient account is rejected. Other patients and clinician accounts remain. Patient/actor references, resource identifiers, IPs and details in affected audit rows are cleared; action/time/type metadata remains. Matching shared organization-history changes are redacted. Privacy-request metadata, the pseudonymous user UUID and a completion receipt containing identifier/object hashes and counts remain under the stated policy. Audit rows remain ordinary database records, not tamper-resistant storage.

The receipt explicitly states `backup_erasure_performed=false`. This tool does not erase database backups/WAL/snapshots, S3 versions, external provider logs, downloads, shared free text, or physical storage remnants. Operators must enforce backup retention, lawful exceptions, provider erasure and restore-time exclusion of erased subjects. Restore into isolation and apply the approved erasure/tombstone procedure before restoring service; this command alone does not make an old backup safe to serve. Full production retention and erasure assurance remains an external deployment gate.
