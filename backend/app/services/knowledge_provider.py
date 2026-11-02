"""Validated providers implement this contract; none is enabled by default."""

from typing import Protocol


class MedicationKnowledgeProvider(Protocol):
    name: str
    version: str

    def review(self, *, terminology_codes: list[dict], documented_allergies: list[dict]) -> list[dict]:
        """Return evidence-linked advisory alerts; never modify orders or medication use.

        Implementations must require approved code/system/evidence mappings, retain provider
        release/evidence references, reject unsupported codes and distinguish unavailable
        knowledge from a negative check. Inputs require explicit authorized scope; no
        unrestricted LLM or patient data transfer is configured by this contract.
        """
        ...
