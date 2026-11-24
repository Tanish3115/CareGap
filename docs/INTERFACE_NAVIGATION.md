# Workspace navigation

The workspace uses a persistent desktop sidebar and an expandable mobile menu. Only the selected section is visible. Clear page headings and an active-menu indicator show the current location. The overview offers direct shortcuts; Upload Document remains available throughout the patient workspace and opens Documents after a successful upload.

Patient digital cards appear in the top-right of the workspace header after sign-in and remain available across sections. The face has visiting-card proportions (3.5 × 2 inches; 336 × 192 CSS pixels at the default browser font size). Smaller screens keep it right-aligned within the available width. They show the patient's name, sharing ID, date of birth, blood group, phone and emergency contact; missing fields display “Not recorded.” The ID can be copied and the profile link opens My profile. Saving profile changes updates the card immediately. Long screen values retain their full text in their title; the image export wraps and fits complete values.

**Download card** produces a 1050 × 600 PNG with 300 DPI metadata, suitable for printing at 3.5 × 2 inches. The browser draws the selected interface language while preserving original names and recorded values. Downloads recheck the current account or patient consent; changing patients cancels pending downloads. Doctors can export only an authorized patient's name and sharing ID. Files already downloaded remain outside revocation, like other patient-approved copies.

Doctors see their own digital card in the same top-right header location, including license number, specialization, affiliation and current professional verification status, even while verification is pending or rejected. Selecting an authorized patient loads that patient's identity card (name and sharing ID) from `/api/v1/patients/{patient_id}/card`. This endpoint checks ownership or verified-doctor status and active consent before lookup, and audits successful views. It does not expose private contact, demographic, ABHA or clinical data. Selecting another patient clears the previous card; Refresh records rechecks access and removes a selection whose grant is no longer active.

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
