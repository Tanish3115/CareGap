"""Offline, release-pinned exact alias mapping. Never guesses similar drug names."""

import hashlib
import json
import unicodedata
from pathlib import Path
from fastapi import HTTPException
from app.config import settings
from app.schemas.terminology import TerminologyCatalog, TerminologyCoding


def normalized_name(value):
    return " ".join(unicodedata.normalize("NFC", value).casefold().split())


def load_catalog():
    mode = settings.TERMINOLOGY_MODE
    if mode == "disabled":
        return None
    if mode == "synthetic":
        value = dict(
            reference="synthetic-terminology-v1",
            release="1",
            entries=[
                dict(
                    aliases=[name],
                    system="urn:caregap:synthetic-medication",
                    code=code,
                    display=name,
                    evidence_reference="urn:caregap:synthetic-fixture:" + code,
                )
                for name, code in [("SYNTHETIC-A", "A"), ("SYNTHETIC-A1", "A1")]
            ],
        )
        raw = json.dumps(value, sort_keys=True).encode()
    else:
        try:
            if (
                not settings.TERMINOLOGY_CATALOG_APPROVED
                or not settings.TERMINOLOGY_APPROVAL_REFERENCE.strip()
            ):
                raise ValueError("Unapproved catalog")
            path = Path(settings.TERMINOLOGY_CATALOG_PATH)
            if not path.is_file() or path.stat().st_size > 5 * 1024 * 1024:
                raise ValueError("Unavailable catalog")
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != settings.TERMINOLOGY_CATALOG_SHA256:
                raise ValueError("Changed catalog")
            value = json.loads(raw)
        except Exception:
            raise HTTPException(
                503, "Terminology catalog unavailable or changed; original names are unchanged"
            ) from None
    try:
        catalog = TerminologyCatalog.model_validate(value)
        identities = [(entry.system, entry.code) for entry in catalog.entries]
        if len(identities) != len(set(identities)):
            raise ValueError("Duplicate identities")
        for entry in catalog.entries:
            if not entry.system.startswith(("https://", "http://", "urn:")):
                raise ValueError("Invalid terminology system")
        return mode, catalog, hashlib.sha256(raw).hexdigest()
    except Exception:
        raise HTTPException(
            503, "Terminology catalog unavailable or changed; original names are unchanged"
        ) from None


def propose(name, loaded=None):
    if loaded is None:
        return dict(state="not_configured", original_name=name, candidates=[], clinical_safety_checked=False)
    mode, catalog, checksum = loaded
    matches = [
        entry
        for entry in catalog.entries
        if normalized_name(name) in {normalized_name(alias) for alias in entry.aliases}
    ]
    if len(matches) > 20:
        return dict(state="ambiguous", original_name=name, candidates=[], clinical_safety_checked=False)
    candidates = [
        TerminologyCoding(
            **entry.model_dump(exclude={"aliases"}),
            release=catalog.release,
            catalog_sha256=checksum,
            mode=mode,
        ).model_dump()
        for entry in matches
    ]
    return dict(
        state="candidate" if len(matches) == 1 else "ambiguous" if matches else "unmatched",
        original_name=name,
        catalog_reference=catalog.reference,
        candidates=candidates,
        clinical_safety_checked=False,
    )


def validate_coding(name, coding, confirm):
    proposal = propose(name, load_catalog())
    identity = coding.model_dump(exclude={"checked", "uncertain"})
    if not any(
        {key: value for key, value in candidate.items() if key not in ("checked", "uncertain")} == identity
        for candidate in proposal["candidates"]
    ):
        raise HTTPException(422, "Terminology coding must match the pinned catalog and exact source name")
    if confirm and (not coding.checked or coding.uncertain):
        raise HTTPException(
            422, "Review the terminology association against its evidence before confirmation"
        )
