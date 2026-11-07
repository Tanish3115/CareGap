"""Pinned offline pair evidence. Absence of a rule is never a negative safety check."""

from datetime import date
import hashlib
from itertools import combinations
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator
from app.config import settings
from app.core.time import utc_now
from app.schemas.terminology import Text, TerminologyCoding
from app.services.medication_terminology import load_catalog, propose


class Code(BaseModel):
    model_config = ConfigDict(extra="forbid")
    system: Text
    code: Text


class PairEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    left: Code
    right: Code
    finding: Literal["advisory", "no_listed_alert"]
    message: Text
    evidence_reference: Text


class KnowledgeCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["caregap-pair-evidence-v1"]
    reference: Text
    release: Text
    license_reference: Text
    clinical_review_reference: Text
    issued_on: date
    expires_on: date
    terminology_catalog_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    pairs: list[PairEvidence] = Field(min_length=1, max_length=20000)

    @model_validator(mode="after")
    def unambiguous_pairs(self):
        seen = set()
        for row in self.pairs:
            left, right = (row.left.system, row.left.code), (row.right.system, row.right.code)
            key = tuple(sorted((left, right)))
            if left == right or key in seen:
                raise ValueError("Pair evidence must be unique and refer to distinct codes")
            seen.add(key)
        if self.issued_on > self.expires_on:
            raise ValueError("Invalid knowledge release period")
        return self


def load_knowledge():
    if settings.KNOWLEDGE_MODE == "disabled":
        return None
    if not settings.KNOWLEDGE_CATALOG_APPROVED or not settings.KNOWLEDGE_APPROVAL_REFERENCE.strip():
        raise ValueError("Knowledge release is not approved")
    path = Path(settings.KNOWLEDGE_CATALOG_PATH)
    if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Knowledge release is unavailable")
    with path.open("rb") as source:
        raw = source.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ValueError("Knowledge release exceeds the size limit")
    checksum = hashlib.sha256(raw).hexdigest()
    if checksum != settings.KNOWLEDGE_CATALOG_SHA256:
        raise ValueError("Knowledge release changed")
    catalog = KnowledgeCatalog.model_validate_json(raw)
    today = utc_now().date()
    if not catalog.issued_on <= today <= catalog.expires_on:
        raise ValueError("Knowledge release is outside its review period")
    return catalog, checksum


def evaluate_knowledge(evidence):
    result = dict(
        status="not_configured",
        reference=None,
        release=None,
        catalog_sha256=None,
        eligible_sources=0,
        excluded_sources=len(evidence),
        assessed_pairs=0,
        unassessed_pairs=0,
        findings=[],
        findings_truncated=False,
        allergy_check="not_evaluated",
        dose_check="not_evaluated",
        clinical_safety_checked=False,
    )
    try:
        loaded = load_knowledge()
        if loaded is None:
            return result
        catalog, checksum = loaded
        terms = load_catalog()
        if terms is None or terms[0] != "approved_catalog" or terms[2] != catalog.terminology_catalog_sha256:
            raise ValueError("Knowledge release requires its approved terminology release")
        indexed = {}
        for item in evidence[:100]:
            try:
                coding = TerminologyCoding.model_validate(item.get("coding"))
                if coding.mode != "approved_catalog" or not coding.checked or coding.uncertain:
                    continue
                identity = coding.model_dump(exclude={"checked", "uncertain"})
                if not any(
                    {k: v for k, v in candidate.items() if k not in {"checked", "uncertain"}} == identity
                    for candidate in propose(item["name"], terms)["candidates"]
                ):
                    continue
                indexed.setdefault((coding.system, coding.code), []).append(item["id"])
            except (ValueError, TypeError, KeyError):
                continue
        pairs = {
            tuple(sorted(((row.left.system, row.left.code), (row.right.system, row.right.code)))): row
            for row in catalog.pairs
        }
        result.update(
            status="available",
            reference=catalog.reference,
            release=catalog.release,
            catalog_sha256=checksum,
            eligible_sources=sum(len(ids) for ids in indexed.values()),
        )
        result["excluded_sources"] -= result["eligible_sources"]
        for left, right in combinations(sorted(indexed), 2):
            row = pairs.get((left, right))
            if row is None:
                result["unassessed_pairs"] += 1
                continue
            result["assessed_pairs"] += 1
            if len(result["findings"]) >= 250:
                result["findings_truncated"] = True
                continue
            result["findings"].append(
                dict(
                    finding=row.finding,
                    message=row.message,
                    evidence_reference=row.evidence_reference,
                    evidence_ids=indexed[left] + indexed[right],
                )
            )
        return result
    except Exception:
        # Missing/changed/expired releases do not erase source comparisons or imply clearance.
        result.update(
            status="unavailable",
            findings=[],
            assessed_pairs=0,
            eligible_sources=0,
            excluded_sources=len(evidence),
        )
        return result
