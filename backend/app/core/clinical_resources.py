"""Stable consent groups; changes require explicit migration of legacy snapshots."""

from typing import Literal

ClinicalResource = Literal[
    "consultations",
    "follow_ups",
    "diagnoses",
    "allergies",
    "labs",
    "care_plans",
    "medications",
    "interventions",
    "source_reviews",
]
CLINICAL_RESOURCES = frozenset(
    (
        "consultations",
        "follow_ups",
        "diagnoses",
        "allergies",
        "labs",
        "care_plans",
        "medications",
        "interventions",
        "source_reviews",
    )
)
KIND_RESOURCE = {
    "diagnosis": "diagnoses",
    "allergy": "allergies",
    "lab": "labs",
    "appointment": "care_plans",
    "referral": "care_plans",
    "test": "care_plans",
    "medication_order": "medications",
    "dispensing": "medications",
    "confirmed_use": "medications",
    "intervention": "interventions",
}


def valid_resources(value):
    if (
        not isinstance(value, list)
        or not value
        or any(not isinstance(item, str) or item not in CLINICAL_RESOURCES for item in value)
    ):
        return set()
    selected = set(value)
    if "interventions" in selected and "care_plans" not in selected:
        return set()
    return selected
