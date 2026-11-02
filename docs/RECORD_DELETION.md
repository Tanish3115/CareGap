# Patient-owned record deletion

Deletion controls are available only in the patient workspace. Clinician upload/write permissions and administrator status do not grant permanent deletion rights. Every API independently checks the authenticated patient owner, and stale confirmations are rejected.

| Location | Action and scope |
| --- | --- |
| Documents | Each card has **Delete document**. Review the current deletion check, acknowledge the warning and choose **Delete permanently**. The database record, processing results, transcription reviews, prescription drafts and unreferenced confirmed prescription entries are removed. Private file cleanup is durably queued. |
| Consultations | Open the consultation and choose **Delete consultation**. Its note revisions and linked follow-ups are removed; original uploads remain. |
| Medications | Open a patient medication-use report and choose **Delete medication report**. All report revisions and its reconciliation history are removed. Historical prescriptions and uploads remain. Both report and review versions must still match. |
| Health records | Open a diagnosis, allergy, lab, appointment, referral, test, medication event or intervention and choose **Delete health record**. Revisions, source associations, import associations and related local reminder receipts are removed. Original uploaded files and retained imported source bundles remain. |
| Consultations: follow-up list | **Delete follow-up** removes that task and its revisions while preserving its consultation. |

The new confirmations include Cancel and a required acknowledgement. They warn that other open record views will refresh, so drafts should be saved first. Successful deletion reloads the current section to clear stale source and record views. Navigating normally between sections still preserves drafts. All controls and primary warnings are translated in the six selected languages.

## Evidence and concurrency protections

- A document referenced by any retained consultation/health-record revision or medication-use report cannot be removed. Explicitly review/delete the dependent record first or use the reviewed privacy procedure. Correcting the latest record does not silently remove source links from its history.
- Active document processing blocks deletion. A server-generated preview fingerprint binds confirmation to the current document, source-review/prescription versions, processing state and dependency counts. Refresh the deletion check after changes.
- Confirmed prescription entries can be removed with their document only if medication-use reports do not depend on them. Independent clinical accounts are never silently cascaded away.
- A care event referenced by an intervention history cannot be removed before those intervention records are explicitly reviewed/deleted. Follow-up deletion locks its parent consultation as well as the task; record deletion locks the expected current version.
- Metadata-only deletion audit events remain. Ordinary record deletion does not erase backups, retained original import bundles, previously downloaded copies or provider-retained object versions. It is distinct from the reviewed account-erasure process in PRIVACY_ERASURE.md.

## Durable private-file cleanup

Migration `0019` adds the private `file_deletions` outbox. Removing the document and creating its cleanup job commit in one database transaction. No file is destroyed before that transaction commits. A failed transaction leaves the source available. A storage failure leaves a pending, retryable cleanup receipt while the deleted document is no longer accessible through the application.

The separate Compose **file-cleanup** service has a writable vault mount; the OCR worker retains its read-only mount. Cleanup checks the patient namespace, active document references, local path/link safety and the local checksum before removing a file. Local case aliases/hard links do not bypass active-source checks. The configured backend stored with that document controls local versus S3 deletion, independently of the current default storage setting. S3 removal concerns the current object; provider versions and retention remain an operator responsibility.

Cleanup is idempotent, uses database row locks with skip-locked support on PostgreSQL, and retries failures after 30 seconds without logging private paths or exception text. Completed receipts clear the private object key and checksum. The patient can expand **Deleted document file cleanup** under Documents and refresh the latest 50 receipts; the status API never exposes storage paths or another patient's receipts.

For an independently managed installation, run `python -m app.file_cleanup` from `backend` alongside the API and OCR worker; `--once` processes one eligible pending item. Inspect unresolved pending receipts and configured storage access before retrying. Never delete objects manually to bypass evidence checks. Pending cleanup blocks reviewed account erasure and prevents migration downgrade, so private files cannot be forgotten by removing their queue.

Consent grants should be revoked, reminders disabled and operational accounts/organizations deactivated through their existing controls. Those records carry authorization or audit history and are not subject to a new blanket Delete button.

Verification includes ownership/role denial, stale report/review/document confirmations, linked historical evidence, rollback/source preservation, checksum/retry/idempotency, storage-backend routing, receipt isolation, account-erasure interlocks, migration preservation/downgrade and end-to-end confirmation/cancellation workflows. All destructive tests use disposable synthetic records.
