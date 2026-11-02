# Consultation and follow-up milestone

Implementation plan, 31 October 2026:

1. Add migration `0005` for encounters, immutable encounter revisions and source-document links, follow-up tasks and immutable task revisions.
2. Extend consent with explicit clinical read/write permissions, both off for existing requests and grants. Clinical access requires an unrestricted `all` document grant so linked sources cannot bypass category or selected-record consent. Document upload permission remains separate.
3. Add authenticated create/read/correct/history APIs, a paginated chronological document/encounter timeline, and follow-up outcomes. Use the shared patient/verified-doctor policy, atomic revision checks and transactional audit events.
4. Build patient and clinician forms, source downloads, correction history and pending/overdue/completed/cancelled follow-ups. Clearly distinguish patient reports from clinician entries; neither is an independent clinical verification.
5. Test ownership, missing/wrong-patient sources, consent boundaries, expiration/revocation, conflicting edits, retained history, migrations and browser workflows.

Encounters and tasks have stable identifiers and a current revision number. Every write appends a complete revision with actor, time, reason and provenance. Corrections never erase previous text or source links. A stale expected version returns HTTP 409. Follow-ups belong to one encounter and patient; outcome reports retain the reporting actor. No automated diagnosis, scheduling, reminders or predictive care-gap claims are introduced.

Clinical sharing includes current and historical encounters, source documents and follow-ups. Patients see this scope before approval. Existing document grants never acquire these permissions implicitly. A patient may correct their own record, including a clinician entry, but the new revision becomes patient-reported and preserves the original clinician revision. Authorized clinicians may create/correct records only with explicit clinical write permission. Operational administrators receive no clinical access.

Acceptance: a synthetic patient links a source to a consultation, corrects it with retained history, tracks a follow-up outcome, and sees chronological records. A verified doctor can read/write only after the corresponding explicit approval; revocation blocks all subsequent reads and writes. Existing document-only sharing still works.

## Patient-owned deletion (current behavior)

The entered-in-error/restoration workflow was removed at the user's request. `DELETE /clinical/encounters/{id}?expected_version=N` permanently removes the patient owner's encounter, every note revision/source association and its follow-up tasks/revisions in one transaction. It retains uploaded source documents and a metadata-only audit event. Doctors and administrators cannot perform this action. A confirmation UI identifies the irreversible effects.

Note corrections, dependent-task writes and deletion serialize on the encounter row, and deletion also checks the version shown to the patient. A stale confirmation is rejected. No application endpoint restores a deleted encounter. Backups have their own retention lifecycle; this is not a complete privacy-erasure workflow. Migration `0006` and its legacy status column remain for database compatibility, while the public controls/routes/filters are removed and existing consultations are visible.
