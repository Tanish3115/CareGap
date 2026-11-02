"""Conservative explicit-label parser. No drug dictionary, inferred doses or LLM."""

import re
from fastapi import HTTPException
from app.schemas.prescription import FIELD_NAMES, PrescriptionItem, PrescriptionContext

LABEL = re.compile(
    r"(?:^|[|;])\s*(medicine|medication|drug|strength|dose|route|frequency|duration|instructions)\s*:\s*([^|;]+)",
    re.I,
)
UNKNOWN = {"?", "unknown", "unclear", "unreadable", "illegible", "not specified", "n/a"}


def extract_explicit_lines(text):
    # A candidate starts only at an explicitly labelled medication name. Following
    # labelled lines may extend it; blank/unlabelled/context lines end the passage.
    blocks, current, offset = [], None, 0
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip("\r\n")
        found = list(LABEL.finditer(line)) if len(line) <= 2000 else []
        names = [match for match in found if match.group(1).lower() in {"medicine", "medication", "drug"}]
        if names:
            if current:
                blocks.append(current)
            current = (offset, line) if len(names) == 1 else None
        elif current and found and line.strip() and len(current[1]) + len(raw) <= 2000:
            current = (current[0], text[current[0] : offset] + line)
        else:
            if current:
                blocks.append(current)
            current = None
        offset += len(raw)
    if current:
        blocks.append(current)
    items = []
    for start, block in blocks[:50]:
        item = dict(source_start=start, source_end=start + len(block))
        repeated = set()
        line_offset = start
        for raw in block.splitlines(keepends=True):
            for match in LABEL.finditer(raw.rstrip("\r\n")):
                key = (
                    "name"
                    if match.group(1).lower() in {"medicine", "medication", "drug"}
                    else match.group(1).lower()
                )
                if key in item or key in repeated:
                    item[key] = None
                    repeated.add(key)
                    continue
                value = match.group(2).strip()
                if value.casefold() in UNKNOWN or len(value) > 500:
                    item[key] = None
                    continue
                begin = line_offset + match.start(2) + len(match.group(2)) - len(match.group(2).lstrip())
                item[key] = dict(
                    value=value, start=begin, end=begin + len(value), checked=False, uncertain=True
                )
            line_offset += len(raw)
        items.append(PrescriptionItem.model_validate(item))
    return items


CONTEXT_LABEL = re.compile(
    r"^\s*(doctor|physician|consultation date|visit date|hospital|clinic|follow[ -]?up|test recommendation|recommended test)\s*:\s*(.+?)\s*$",
    re.I,
)
CONTEXT_KEYS = {
    "doctor": "doctor_name",
    "physician": "doctor_name",
    "consultation date": "consultation_date",
    "visit date": "consultation_date",
    "hospital": "clinic",
    "clinic": "clinic",
    "follow-up": "follow_up_instructions",
    "follow up": "follow_up_instructions",
    "followup": "follow_up_instructions",
    "test recommendation": "test_recommendations",
    "recommended test": "test_recommendations",
}


def extract_context(text):
    values = {}
    repeated = set()
    offset = 0
    for raw in text.splitlines(keepends=True):
        match = CONTEXT_LABEL.fullmatch(raw.rstrip("\r\n"))
        if match:
            key = CONTEXT_KEYS[match.group(1).lower()]
            value = match.group(2)
            if len(value) <= 500 and value.strip().casefold() not in UNKNOWN:
                start = offset + match.start(2)
                evidence = dict(
                    value=value, start=start, end=start + len(value), checked=False, uncertain=True
                )
                if key in ("follow_up_instructions", "test_recommendations"):
                    if len(values.setdefault(key, [])) < 20:
                        values[key].append(evidence)
                elif key in values or key in repeated:
                    values[key] = None
                    repeated.add(key)
                else:
                    values[key] = evidence
        offset += len(raw)
    return PrescriptionContext.model_validate(values)


def validate_context(context, source, confirm=False):
    for value in context.model_dump().values():
        for field in value if isinstance(value, list) else [value] if value else []:
            if (
                not 0 <= field["start"] < field["end"] <= len(source)
                or source[field["start"] : field["end"]] != field["value"]
                or "\x00" in field["value"]
            ):
                raise HTTPException(422, "Prescription context must match its exact source span")
            if confirm and (
                not field["checked"] or field["uncertain"] or field["value"].strip().casefold() in UNKNOWN
            ):
                raise HTTPException(
                    422, "Review every supplied prescription context value before confirmation"
                )


def validate_items(items, source, confirm=False, acknowledge_missing=False):
    seen = set()
    for item in items:
        if item.coding:
            if item.name is None:
                raise HTTPException(422, "A source medication name is required for terminology mapping")
            from app.services.medication_terminology import validate_coding

            validate_coding(item.name.value, item.coding, confirm)
        if (
            not 0 <= item.source_start < item.source_end <= len(source)
            or item.source_end - item.source_start > 2000
        ):
            raise HTTPException(422, "Every row needs an exact, bounded source passage")
        for field in FIELD_NAMES:
            evidence = getattr(item, field)
            if evidence is None:
                continue
            if not evidence.value.strip():
                raise HTTPException(422, "Blank source values must be left missing")
            if (
                not item.source_start <= evidence.start < evidence.end <= item.source_end
                or source[evidence.start : evidence.end] != evidence.value
            ):
                raise HTTPException(
                    422,
                    f"{field} must match its exact source span; invented or normalized values are not accepted",
                )
            if "\x00" in evidence.value:
                raise HTTPException(422, "Source values contain unsupported control characters")
            if confirm and (
                not evidence.checked or evidence.uncertain or evidence.value.casefold().strip() in UNKNOWN
            ):
                raise HTTPException(
                    422,
                    "Check every supplied value against the source and resolve uncertainty before confirmation",
                )
        signature = tuple(
            (getattr(item, field).start, getattr(item, field).end) if getattr(item, field) else None
            for field in FIELD_NAMES
        )
        if signature in seen:
            raise HTTPException(422, "The same source fields cannot be entered twice")
        seen.add(signature)
        if confirm and item.name is None:
            raise HTTPException(422, "A source-supported medication name is required for confirmation")
        if confirm and any(getattr(item, field) is None for field in FIELD_NAMES) and not acknowledge_missing:
            raise HTTPException(422, "Acknowledge missing source fields; do not invent them")
    if confirm and not items:
        raise HTTPException(422, "At least one source-supported entry is required")


def missing_fields(item):
    return [field for field in FIELD_NAMES if getattr(item, field) is None]
