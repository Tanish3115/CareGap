# Clinical sharing and the unified timeline

Implemented locally on 1 November 2026. No GitHub push is authorized.

Doctors can request a specific set of clinical groups. Patients can remove groups before approving. Clinical viewing and writing remain separate from document upload permission. Write permission applies only to the approved groups and does not let clinicians rewrite patient-owned medication accounts or delete consultations.

| Clinical group | Records and histories covered |
| --- | --- |
| Consultation notes | Consultations, attributed corrections and source associations |
| Consultation follow-ups | Consultation-linked tasks and reported outcomes |
| Diagnoses and conditions | Structured diagnosis accounts |
| Allergies and reactions | Structured allergy/reaction accounts |
| Lab results | Structured literal lab results |
| Appointments, referrals and tests | Recorded care plans, outcomes, rescheduling and local reminder history |
| Medication history and reconciliation | Confirmed historical prescription entries, patient use accounts, clinician reconciliation, medication orders, dispensing and clinician use accounts |
| Staff interventions and outcomes | Version-bound intervention events and descriptive outcome extracts; also requires linked care-plan access |
| Document transcription reviews | Reviewed source text and its revision history |

Prescription drafts and their histories require both medications and document transcription reviews. Creating or correcting drafts requires writing access to both; confirmation still requires a verified clinician. Medication comparison excludes allergy records unless the allergies group is also approved, and the response/UI explicitly identifies that exclusion.

**Original document consent remains separate in meaning:** clinical sharing currently requires an unrestricted all-document grant. Selecting only labs limits the additional structured records and histories; the approved original PDFs/images can still contain other clinical information. Both request and approval screens disclose this. Clinical group controls do not redact original documents, remove downloaded copies or establish an organization-wide permission.

Every source/history/read/write request rechecks patient ownership or active verified-doctor consent, expiration, revocation and applicable organization membership. Effective permissions are the union of eligible grants, with read and write calculated separately. Aggregate lists, summaries, FHIR exports and the unified timeline filter unauthorized groups in SQL before pagination. Original imported FHIR JSON requires every clinical group represented by that source; a lab grant cannot retrieve a mixed lab/condition source. Imports check all required write groups before saving anything.

Migration `0015` snapshots the nine existing groups on earlier clinical requests/grants. Document-only grants stay document-only; identifiers and record histories are preserved. New requests also store an explicit snapshot. Missing, empty, malformed or unknown stored scopes fail closed. Future groups require an explicit consent/migration decision. Downgrading disables restricted or malformed clinical permissions rather than silently turning them into legacy all-clinical grants; upgrading again does not resurrect those disabled permissions.

## Unified medical timeline

Patients and consented doctors have one searchable, paginated timeline of authorized current document, consultation, follow-up, structured record, care-plan, patient medication account, confirmed historical prescription and transcription-review entries. Type and date filters run before pagination. Stable date/type/identifier ordering avoids duplicate revision entries.

Each item states its date basis: a source clinical date, upload date when missing, consultation/record/report date, or planned due date. Due dates do not establish attendance; historical prescriptions do not establish current use. Opening an item loads its authorized source, readable recorded fields, original download when applicable and paginated version history. Earlier versions stay in source history rather than multiplying the main timeline. Consent revocation blocks fresh timeline/source/history requests. The interface clears selected records when refreshed permissions change.

The previous consultation workspace remains available for its editing, follow-up and patient deletion actions. Permanent consultation deletion retains original uploaded documents and a metadata-only audit event.
