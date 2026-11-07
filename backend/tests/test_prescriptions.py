from copy import deepcopy
import pytest
from fastapi import HTTPException
from app.models.document import MedicalDocument
from app.services.storage_service import storage_service
from app.models.prescription import MedicationEntry, PrescriptionRevision
from app.schemas.prescription import PrescriptionItem
from app.services.prescription_extraction import extract_explicit_lines, validate_items
from tests.test_document_reviews import processed, payload as review_payload
from tests.test_hardening import admin_token as admin_token, grant, headers

TEXT = "Synthetic source 🧪\nMedicine: SYNTHETIC-A | Dose: 1 unit | Frequency: nightly\nDrug: SYNTHETIC-A1 | Strength: 20 units"


def setup_source(client, token, db, text=TEXT):
    doc = processed(client, token, db)
    url = f"/api/v1/documents/{doc['id']}/prescription"
    reviewed = client.post(
        url.replace("/prescription", "/review"),
        headers=headers(token),
        json=review_payload(reviewed_text=text),
    )
    assert reviewed.status_code == 201, reviewed.text
    return doc, url


def generate(client, token, url, version=0, source=1):
    response = client.post(
        url + "/generate",
        headers=headers(token),
        json=dict(expected_version=version, source_review_version=source),
    )
    assert response.status_code == 201, response.text
    return response.json()


def save_payload(draft, confirm=False):
    items = deepcopy(draft["items"])
    if confirm:
        for item in items:
            for value in item.values():
                if isinstance(value, dict):
                    value.update(checked=True, uncertain=False)
    return dict(
        expected_version=draft["version"],
        source_review_version=draft["source_review_version"],
        items=items,
        reason="Compared synthetic original and patient association",
        source_checked=True,
        confirm=confirm,
        missing_fields_acknowledged=True,
    )


def test_drafts_preserve_missing_exact_fields_and_patient_cannot_confirm(
    client, patient_token, patient_user, db_session
):
    doc, url = setup_source(client, patient_token, db_session)
    draft = generate(client, patient_token, url)
    assert draft["state"] == "draft" and not draft["can_confirm"]
    assert [row["name"]["value"] for row in draft["items"]] == ["SYNTHETIC-A", "SYNTHETIC-A1"]
    assert draft["items"][0]["strength"] is None
    for item in draft["items"]:
        for evidence in item.values():
            if isinstance(evidence, dict):
                assert TEXT[evidence["start"] : evidence["end"]] == evidence["value"]
                assert not evidence["checked"] and evidence["uncertain"]
    assert client.post(url, headers=headers(patient_token), json=save_payload(draft, True)).status_code == 403
    saved = client.post(url, headers=headers(patient_token), json=save_payload(draft))
    assert saved.status_code == 201 and saved.json()["version"] == 2
    assert db_session.query(MedicationEntry).count() == 0
    assert (
        client.get(
            f"/api/v1/medications?patient_id={patient_user.patient_profile.id}",
            headers=headers(patient_token),
        ).json()
        == []
    )
    assert client.post(url, headers=headers(patient_token), json=save_payload(draft)).status_code == 409


def test_clinician_confirmation_retains_history_and_flags_pending_or_changed_source(
    client,
    patient_token,
    doctor_token,
    patient_user,
    doctor_user,
    db_session,
):
    doc, url = setup_source(client, patient_token, db_session)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, url)
    unchecked = save_payload(draft)
    unchecked["confirm"] = True
    assert client.post(url, headers=headers(doctor_token), json=unchecked).status_code == 422
    checked = save_payload(draft, True)
    checked["missing_fields_acknowledged"] = False
    assert client.post(url, headers=headers(doctor_token), json=checked).status_code == 422
    checked["missing_fields_acknowledged"] = True
    response = client.post(url, headers=headers(doctor_token), json=checked)
    assert response.status_code == 201, response.text
    assert response.json()["state"] == "clinician_confirmed"
    meds = f"/api/v1/medications?patient_id={patient_user.patient_profile.id}&document_id={doc['id']}"
    entries = client.get(meds, headers=headers(patient_token)).json()
    assert len(entries) == 2 and all(row["record_kind"] == "documented_prescription" for row in entries)
    assert all(row["needs_clarification"] and not row["draft_pending"] for row in entries)
    assert next(row for row in entries if row["name"] == "SYNTHETIC-A")["strength"] is None
    newer = generate(client, patient_token, url, version=2)
    assert all(row["draft_pending"] for row in client.get(meds, headers=headers(doctor_token)).json())
    newer["items"] = newer["items"][:1]
    confirmed = client.post(url, headers=headers(doctor_token), json=save_payload(newer, True))
    assert confirmed.status_code == 201, confirmed.text
    assert len(client.get(meds, headers=headers(patient_token)).json()) == 1
    assert db_session.query(MedicationEntry).count() == 3  # prior confirmation preserved
    changed = client.post(
        url.replace("/prescription", "/review"),
        headers=headers(patient_token),
        json=review_payload(expected_version=1, reviewed_text=TEXT + "\nSynthetic correction"),
    )
    assert changed.status_code == 201
    assert client.get(url, headers=headers(patient_token)).json()["source_stale"]
    assert client.get(meds, headers=headers(patient_token)).json()[0]["source_stale"]
    stale = save_payload(confirmed.json(), True)
    assert client.post(url, headers=headers(doctor_token), json=stale).status_code == 409
    assert [
        row["version"] for row in client.get(url + "/history", headers=headers(patient_token)).json()
    ] == [4, 3, 2, 1]


def test_exact_spans_and_duplicate_evidence_cannot_be_forged(client, patient_token, db_session):
    _, url = setup_source(client, patient_token, db_session)
    draft = generate(client, patient_token, url)
    for change in ("invented", "outside", "duplicate", "source_ack", "extra"):
        data = save_payload(draft)
        if change == "invented":
            data["items"][0]["name"]["value"] = "INVENTED"
        elif change == "outside":
            data["items"][0]["source_end"] = 5
        elif change == "duplicate":
            data["items"].append(deepcopy(data["items"][0]))
        elif change == "source_ack":
            data["source_checked"] = False
        else:
            data["patient_id"] = "forged"
        assert client.post(url, headers=headers(patient_token), json=data).status_code == 422, change
    assert db_session.query(PrescriptionRevision).count() == 1


def test_prescription_routes_enforce_consent_verification_and_revocation(
    client,
    patient_token,
    second_patient_token,
    doctor_token,
    admin_token,
    patient_user,
    doctor_user,
    db_session,
):
    _, url = setup_source(client, patient_token, db_session)
    draft = generate(client, patient_token, url)
    meds = f"/api/v1/medications?patient_id={patient_user.patient_profile.id}"

    def denied(token):
        for path in (url, url + "/history", meds):
            assert client.get(path, headers=headers(token)).status_code == 403
        assert client.post(url, headers=headers(token), json=save_payload(draft)).status_code == 403
        assert (
            client.post(
                url + "/generate",
                headers=headers(token),
                json=dict(expected_version=1, source_review_version=1),
            ).status_code
            == 403
        )

    for token in (second_patient_token, doctor_token, admin_token):
        denied(token)
    grant(db_session, patient_user, doctor_user, scope="prescriptions_only")
    denied(doctor_token)  # source permission alone is insufficient
    clinical = grant(db_session, patient_user, doctor_user, include_clinical_records=True)
    assert client.get(url, headers=headers(doctor_token)).status_code == 200
    assert client.post(url, headers=headers(doctor_token), json=save_payload(draft, True)).status_code == 403
    clinical.allow_clinical_write = True
    doctor_user.doctor_profile.verification_status = "pending"
    db_session.commit()
    denied(doctor_token)
    doctor_user.doctor_profile.verification_status = "verified"
    clinical.is_revoked = True
    db_session.commit()
    denied(doctor_token)


def test_parser_rejects_unsupported_layouts_and_preserves_uncertainty():
    assert extract_explicit_lines("SYNTHETIC 10 mg twice a day\nTake one at bedtime") == []
    rows = extract_explicit_lines("Medicine: SYNTHETIC | Strength: unknown | Dose: 1 unit | Dose: 2 units")
    assert rows[0].strength is None and rows[0].dose is None
    assert extract_explicit_lines("Medicine: A | Drug: B") == []
    source = "Unlabelled SYNTHETIC item"
    manual = PrescriptionItem(
        source_start=0, source_end=len(source), name=dict(value="SYNTHETIC", start=11, end=20)
    )
    validate_items([manual], source)
    with pytest.raises(HTTPException, match="Check every supplied"):
        validate_items([manual], source, confirm=True, acknowledge_missing=True)


def test_missing_review_nonprescription_and_tampered_original_fail_closed(client, patient_token, db_session):
    doc = processed(client, patient_token, db_session)
    url = f"/api/v1/documents/{doc['id']}/prescription"
    assert (
        client.post(
            url + "/generate",
            headers=headers(patient_token),
            json=dict(expected_version=0, source_review_version=1),
        ).status_code
        == 409
    )
    assert (
        client.post(
            url.replace("/prescription", "/review"),
            headers=headers(patient_token),
            json=review_payload(reviewed_text=TEXT),
        ).status_code
        == 201
    )
    entity = db_session.get(MedicalDocument, doc["id"])
    entity.document_type = "other"
    db_session.commit()
    assert client.get(url, headers=headers(patient_token)).status_code == 422
    entity.document_type = "prescription"
    db_session.commit()
    path = storage_service.resolve(entity.file_path)
    original = path.read_bytes()
    try:
        path.write_bytes(b"Synthetic tampering")
        assert (
            client.post(
                url + "/generate",
                headers=headers(patient_token),
                json=dict(expected_version=0, source_review_version=1),
            ).status_code
            == 400
        )
        assert db_session.query(PrescriptionRevision).count() == 0
    finally:
        path.write_bytes(original)


def test_repeated_names_require_acknowledgement_and_remain_separate_source_rows(
    client,
    patient_token,
    doctor_token,
    patient_user,
    doctor_user,
    db_session,
):
    line = "Medicine: SYNTHETIC | Strength: 1 unit | Dose: 1 unit | Route: source route | Frequency: source frequency | Duration: source duration | Instructions: source instruction"
    _, url = setup_source(client, patient_token, db_session, line + "\n" + line)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    draft = generate(client, patient_token, url)
    data = save_payload(draft, True)
    data["missing_fields_acknowledged"] = False
    assert client.post(url, headers=headers(doctor_token), json=data).status_code == 422
    data["missing_fields_acknowledged"] = True
    saved = client.post(url, headers=headers(doctor_token), json=data)
    assert saved.status_code == 201, saved.text
    assert db_session.query(MedicationEntry).count() == 2
    assert all(row.needs_clarification for row in db_session.query(MedicationEntry))
