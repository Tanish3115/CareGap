# Optional ABDM integration preparation

Live ABDM/ABHA is not configured, and no endpoint fabricates ABDM success. The master prompt makes this integration optional and requires actual authorization/conformance before a live-access claim. Local UUIDs and the user's requested A123 sharing codes are not ABHA identities. Local grants and exported FHIR Consent records are not ABDM consent artifacts.

The reusable implemented boundary is the authenticated, patient-scoped FHIR adapter with original-source retention, immutable import lineage, bounded pages, current/history provenance, explicit medication distinctions and patient-owned consent export. Imports cannot create permissions. Unknown resource mappings are rejected rather than guessed.

Before selecting a live adapter, the operator must establish the approved institutional HIP/HIU roles, official sandbox access, identity proofing/linking, processor/privacy review and the receiving system's current implementation-guide/version requirements. The adapter must then be tested for its authenticated callback/consent lifecycle, patient and record linkage, purpose/date/resource restrictions, revocation, replay/idempotency, encrypted transport, error redaction and audit boundaries. The exact external API contract must come from the approved current sandbox specification; this document does not invent one.

No ABHA value, credential, identifier or clinical record is transmitted by the current local-test configuration. Further work is conditional on choosing and authorizing this optional external integration, not an invisible enabled feature.
