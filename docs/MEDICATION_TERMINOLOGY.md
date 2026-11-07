# Source-bound medication terminology

The local prescription workflow can propose exact medication-name aliases from a versioned offline catalog. It never guesses a spelling, strength, ingredient, dose, therapeutic equivalence or current use. The original name, text spans and original document remain unchanged. An empty match is unknown, not a safety clearance.

`TERMINOLOGY_MODE=disabled` is the default. `synthetic` enables only the explicitly artificial `SYNTHETIC-A` and `SYNTHETIC-A1` fixtures under `urn:caregap:synthetic-medication`; similar names do not match. This vocabulary is not a real medicine database. The browser-test environment selects this mode only for disposable synthetic sources.

For an independently approved licensed terminology release, use `TERMINOLOGY_MODE=approved_catalog`, a private `TERMINOLOGY_CATALOG_PATH`, its exact SHA-256 in `TERMINOLOGY_CATALOG_SHA256`, `TERMINOLOGY_CATALOG_APPROVED=true` and a `TERMINOLOGY_APPROVAL_REFERENCE`. These are operator assertions, not clinical certification. The file is bounded to 5 MiB/20,000 entries, validated on every lookup and rejected if it changes. There is no external patient-data transmission or network terminology request.

Example catalog structure, using artificial identifiers only:

```json
{
  "reference": "SYNTHETIC-EXAMPLE-ONLY",
  "release": "test-1",
  "entries": [{
    "aliases": ["SYNTHETIC-SOURCE"],
    "system": "urn:test:terminology",
    "code": "TEST-1",
    "display": "Synthetic canonical name",
    "evidence_reference": "urn:test:evidence:1"
  }]
}
```

Alias comparison applies Unicode NFC, case folding and whitespace normalization only. Multiple exact matches remain separate candidates. Duplicate code/system entries, invalid files and unapproved/changed releases fail closed. No unrestricted language model or fuzzy drug matching is involved.

In a prescription row, select **Find terminology candidates**, inspect the system/code/release and evidence, then explicitly review the association. The source name must still match its exact reviewed transcription span. Patients may save a proposed coding in a draft; only an authorized verified clinician can confirm it with the historical source prescription. Confirmation rechecks the pinned catalog and requires a checked, resolved mapping. Reloading a review clears the reviewer's checkboxes. Changing the source name clears the proposed mapping.

Coding snapshots are stored within existing versioned prescription evidence. Old confirmations and evidence remain retained even after changing providers. Latest documented-entry output includes the confirmed snapshot. Longitudinal FHIR export keeps the original medication text and includes only checked/resolved coding plus evidence; synthetic mappings retain an explicit synthetic note. The export uses the [FHIR R4 Coding datatype](https://hl7.org/fhir/R4/datatypes.html#Coding); this does not establish external implementation-guide conformance.

The mapping does not activate clinical interaction, allergy cross-reactivity or safe-dose checks. Those still require an approved medication knowledge provider. Tests cover similar names, unavailable knowledge, ambiguous aliases, pinned-release changes, forged codes, patient/doctor/admin permissions, current-source checks, historical persistence and FHIR preservation.
