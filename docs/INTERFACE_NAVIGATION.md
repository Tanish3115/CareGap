# Workspace navigation

The workspace uses a persistent desktop sidebar and an expandable mobile menu. Only the selected section is visible. Clear page headings and an active-menu indicator show the current location. The overview offers direct shortcuts; Upload Document remains available throughout the patient workspace and opens Documents after a successful upload.

| Patient section | Features |
| --- | --- |
| Overview | Document and sharing counts, account identity, quick actions |
| Documents | Search, category filters, uploads/downloads, processing, transcription review, prescription drafts and confirmed entries |
| Timeline | Combined medical timeline, filters, source inspection and histories |
| Consultations | Consultation notes, corrections, follow-ups and patient-owned deletion |
| Medications | Patient medication-use reports, comparisons and clinician reconciliation |
| Health records | Diagnoses, allergies, lab text, appointments, referrals, tests and care events |
| Care & reminders | Worklist, local reminder preferences/history, source assistance, comparison indicators, FHIR exchange and synthetic research |
| Sharing & access | Patient sharing ID, access requests, consent grants/revocation and access history |
| My profile | Editable health profile |
| Privacy & data | Personal data exports and privacy review requests |

Clinicians have Patient access plus Documents, Timeline, Consultations, Medications, Health records and Care & reminders. The authorized-patient selector stays available across these destinations. Selecting a different patient or receiving changed capabilities keeps the existing source/scope component keys and API checks. A feature outside the approved clinical scope displays an explanatory notice. Menu visibility does not grant access.

Administrators have separate Professional verification, Organization and user operations, and Operational audit destinations. The sidebar does not add clinical privileges.

Section links support browser Back/Forward, reloads and direct URLs such as `/dashboard#documents`. Unknown or wrong-role section names recover to the role's starting destination. Navigation hides sections without unmounting their forms: unsaved drafts survive switching sections and browser history within the page, but are not saved across reloads. No clinical data is stored in browser storage for navigation.

All menu labels, headings and instructions use the existing six-language catalogs. Original source text and patient identifiers stay unchanged. Mobile menus expose expanded state, close after selection, and support Escape with focus returning to the menu button. Keyboard focus indicators, a skip-to-content control, larger form targets and reduced-motion preferences are supported.

Browser coverage includes section isolation, retained drafts, history, reloads, every patient destination, profile availability, mobile expansion/Escape, invalid destinations and horizontal-overflow checks. Existing upload, clinical, sharing, reconciliation and deletion workflows now navigate through the sidebar while retaining their previous assertions. Automated accessibility checks cover public pages, every synthetic patient section, the upload dialog and the expanded mobile menu; they do not replace independent assistive-technology review.
