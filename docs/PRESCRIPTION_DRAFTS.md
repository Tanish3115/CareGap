# Source-grounded prescription drafts

31 October 2026. Local implementation only; no GitHub push is authorized.

Implement one testable slice: reviewed source transcription → conservative explicit-label extraction/manual source-bound editing → versioned draft → clinician-reviewed historical prescription entries.

The local parser recognizes labelled `Medicine:`, `Drug:` or `Medication:` lines with optional `Strength:`, `Dose:`, `Route:`, `Frequency:`, `Duration:` and `Instructions:` fields separated by `|` or `;`. It is not an unrestricted LLM, drug dictionary or general handwriting interpreter. Unsupported layouts remain manual work, never fabricated results. Every supplied value must match an exact Unicode-code-point span inside its cited source line. Missing values stay null. Generated values start uncertain and unchecked.

Drafts reference an immutable source-review revision, checksum, author and reason. A changed source review makes the draft stale; regeneration creates another revision rather than replacing history. Patients and clinically authorized doctors can edit. Only verified doctors with source access and explicit clinical write consent can confirm. Confirmation requires checking present values against the source, acknowledging missing values and source/patient association. Unreadable/unknown name placeholders cannot become medication names.

Confirmation creates relational `documented_prescription` entries linked to the confirmed revision. They describe the source document, not a new order, dispensing event, current use or a safe dose. Missing fields produce a clarification flag. Reconfirmation supersedes the displayed earlier version through a latest-confirmed-revision query; earlier entries remain in history. A newer unconfirmed draft or source transcription is explicitly flagged. Current-use/reconciliation workflows and terminology normalization remain later work.

Tests must cover exact source spans, wrong-patient sources, missing strength, lookalike names, duplicate rows, unsupported layouts, invalid/ambiguous offsets, stale source/draft versions, patient/doctor/admin access, clinician-only confirmation, revocation, retained revisions, migrations and browser use. No clinical effectiveness or validated prescribing safety is claimed.
