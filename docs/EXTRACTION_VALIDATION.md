# Extraction evaluation and independent review

`scripts/evaluate_extraction.py` evaluates the existing conservative explicit-label text extractor against offline annotations without importing or querying the patient database. It does not obtain clinical approval, manufacture a clinical dataset, or claim handwriting/OCR accuracy from text-only tests.

Run the synthetic software fixture from the project root:

```powershell
backend/.venv/Scripts/python.exe scripts/evaluate_extraction.py --output .tools/research/extraction-fixture.json
```

The 13 fixtures check labelled extraction, missing/unclear fields, unsupported text and preservation of Unicode medication tokens in the six selected language groups. English field labels are used; this is not evidence of general extraction quality in those languages. The report identifies its mode as `synthetic_only` and always keeps clinical validation and production approval false.

For an approved review, supply `--dataset <private-json>`. The strict envelope includes `mode=approved_deidentified`, an approval reference, an independent annotation reference and cases with opaque 64-character hexadecimal IDs, a selected language, source text and an `expected` list of medication fields. Allowed fields are name, strength, dose, route, frequency, duration and instructions; unavailable fields are null. Patient names/IDs are not case identifiers. De-identification and approval must be performed by the responsible data/review team; the schema cannot independently establish that the source is free of identifying information.

Keep raw reviewed cases in a private directory such as ignored `.tools/approved-data`, outside source and package paths. Input files are capped at 20 MiB and 10,000 cases, with bounded text/row sizes. Repeated case identifiers and unknown annotation fields are rejected. Validation failures do not print dataset contents. Reports omit raw source, medication values and case identifiers; checksums bind source text and the complete annotated envelope. A new output is created exclusively with restricted permissions; existing reports are never overwritten.

Metrics include exact case agreement, exact row/field precision and recall, false positives/negatives, falsely populated missing fields, invalid source spans and language-group counts. Incorrect values count as both a false positive and false negative. Empty precision/recall denominators stay null. Annotations are aligned by source row order, with row-count mismatches treated as case failures. A high synthetic score never sets clinical approval.

Remaining independent validation should use representative approved sources, handwriting/scan-quality strata, clinician-adjudicated annotations, medication look-alike/conflict cases, scope/identity/source-association cases, subgroup/sample-size planning and prospective workflow review. Protocol thresholds and acceptable error consequences must be agreed by qualified reviewers before examining holdout results. OCR/handwriting, clinical correctness, risk-model outcomes and intervention effectiveness require their own data and review; this explicit-label benchmark cannot substitute for them.
