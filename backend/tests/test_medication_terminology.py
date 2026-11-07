from copy import deepcopy
import hashlib
import json
import pytest
from fastapi import HTTPException
from app.config import settings
from app.models.document import MedicalDocument
from app.services.medication_terminology import load_catalog, propose
from tests.test_prescriptions import setup_source, generate, save_payload
from tests.test_hardening import grant, headers, admin_token as admin_token


def synthetic(monkeypatch):
    monkeypatch.setattr(settings, "TERMINOLOGY_MODE", "synthetic")


def test_exact_names_remain_distinct_and_missing_knowledge_is_not_clearance(monkeypatch):
    synthetic(monkeypatch)
    catalog = load_catalog()
    assert propose(" SYNTHETIC-A ", catalog)["candidates"][0]["code"] == "A"
    assert propose("SYNTHETIC-A1", catalog)["candidates"][0]["code"] == "A1"
    for name in ("SYNTHETIC-AI", "unclear", "?", "real medicine", "SYNTHETIC-A 10mg"):
        result = propose(name, catalog)
        assert (
            result["state"] == "unmatched"
            and result["candidates"] == []
            and not result["clinical_safety_checked"]
        )
    assert propose("SYNTHETIC-A")["state"] == "not_configured"


def approved(monkeypatch, tmp_path, *, ambiguous=False):
    entries = [
        dict(
            aliases=["SYNTHETIC-SOURCE"],
            code="TEST-1",
            system="urn:test:terminology",
            display="Synthetic canonical",
            evidence_reference="urn:test:evidence",
        )
    ]
    if ambiguous:
        entries.append(dict(entries[0], code="TEST-2"))
    raw = json.dumps(dict(reference="TEST-APPROVAL-REFERENCE", release="test-1", entries=entries)).encode()
    path = tmp_path / "test-catalog.json"
    path.write_bytes(raw)
    for key, value in dict(
        TERMINOLOGY_MODE="approved_catalog",
        TERMINOLOGY_CATALOG_PATH=str(path),
        TERMINOLOGY_CATALOG_SHA256=hashlib.sha256(raw).hexdigest(),
        TERMINOLOGY_CATALOG_APPROVED=True,
        TERMINOLOGY_APPROVAL_REFERENCE="SYNTHETIC-TEST-ONLY",
    ).items():
        monkeypatch.setattr(settings, key, value)
    return path


def test_approved_catalog_pins_release_and_preserves_ambiguity(monkeypatch, tmp_path):
    path = approved(monkeypatch, tmp_path, ambiguous=True)
    result = propose("SYNTHETIC-SOURCE", load_catalog())
    assert result["state"] == "ambiguous" and len(result["candidates"]) == 2
    assert all(
        not item["checked"] and item["uncertain"] and item["release"] == "test-1"
        for item in result["candidates"]
    )
    path.write_text("{}")
    with pytest.raises(HTTPException) as error:
        load_catalog()
    assert error.value.status_code == 503


def test_unapproved_or_duplicate_catalog_fails_closed(monkeypatch, tmp_path):
    approved(monkeypatch, tmp_path)
    monkeypatch.setattr(settings, "TERMINOLOGY_CATALOG_APPROVED", False)
    with pytest.raises(HTTPException):
        load_catalog()


def test_source_bound_proposal_confirmation_and_history(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session, monkeypatch
):
    synthetic(monkeypatch)
    doc, url = setup_source(client, patient_token, db_session)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, url)
    result = client.post(
        url + "/terminology",
        headers=headers(patient_token),
        json=dict(source_review_version=1, items=draft["items"]),
    )
    assert result.status_code == 200, result.text
    assert result.json()["mode"] == "synthetic" and result.json()["requires_clinician_review"]
    coding = result.json()["rows"][0]["candidates"][0]
    payload = save_payload(draft, True)
    payload["items"][0]["coding"] = coding
    assert client.post(url, headers=headers(doctor_token), json=payload).status_code == 422
    payload["items"][0]["coding"].update(checked=True, uncertain=False)
    assert client.post(url, headers=headers(patient_token), json=payload).status_code == 403
    response = client.post(url, headers=headers(doctor_token), json=payload)
    assert response.status_code == 201, response.text
    entries = client.get(
        f"/api/v1/medications?patient_id={patient_user.patient_profile.id}", headers=headers(patient_token)
    ).json()
    entry = next(item for item in entries if item["name"] == "SYNTHETIC-A")
    assert entry["coding"]["code"] == "A" and entry["name"] == "SYNTHETIC-A"
    assert entry["coding"]["mode"] == "synthetic" and entry["coding"]["checked"]
    assert (
        client.get(url + "/history", headers=headers(patient_token)).json()[0]["items"][0]["coding"][
            "catalog_sha256"
        ]
        == coding["catalog_sha256"]
    )
    exported = client.get(
        "/api/v1/clinical/fhir/longitudinal",
        params=dict(patient_id=patient_user.patient_profile.id),
        headers=headers(patient_token),
    )
    assert exported.status_code == 200, exported.text
    medication = next(
        row["resource"] for row in exported.json()["entry"] if row["resource"].get("id") == entry["id"]
    )
    assert medication["medicationCodeableConcept"]["text"] == "SYNTHETIC-A"
    assert (
        medication["medicationCodeableConcept"]["coding"][0]["system"] == "urn:caregap:synthetic-medication"
    )
    assert any("Synthetic terminology fixture" in note["text"] for note in medication["note"])


@pytest.mark.parametrize("mutation", ["name", "code", "release", "hash"])
def test_forged_or_mismatched_codings_cannot_be_saved(
    client, patient_token, db_session, monkeypatch, mutation
):
    synthetic(monkeypatch)
    _, url = setup_source(client, patient_token, db_session)
    draft = generate(client, patient_token, url)
    payload = save_payload(draft)
    coding = propose("SYNTHETIC-A", load_catalog())["candidates"][0]
    if mutation == "name":
        payload["items"][1]["coding"] = coding
    else:
        coding[{"hash": "catalog_sha256"}.get(mutation, mutation)] = (
            "0" * 64 if mutation == "hash" else "FORGED"
        )
        payload["items"][0]["coding"] = coding
    assert client.post(url, headers=headers(patient_token), json=payload).status_code == 422


def test_lookup_requires_current_authorized_source_not_an_arbitrary_name(
    client, patient_token, doctor_token, admin_token, patient_user, doctor_user, db_session, monkeypatch
):
    synthetic(monkeypatch)
    doc, url = setup_source(client, patient_token, db_session)
    draft = generate(client, patient_token, url)
    body = dict(source_review_version=1, items=draft["items"])
    for token in (doctor_token, admin_token):
        assert client.post(url + "/terminology", headers=headers(token), json=body).status_code == 403
    forged = deepcopy(body)
    forged["items"][0]["name"]["value"] = "SYNTHETIC-A1"
    assert client.post(url + "/terminology", headers=headers(patient_token), json=forged).status_code == 422
    db_session.get(MedicalDocument, doc["id"]).review_version = 2
    db_session.commit()
    assert client.post(url + "/terminology", headers=headers(patient_token), json=body).status_code == 409
