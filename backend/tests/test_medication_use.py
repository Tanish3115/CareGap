from datetime import timedelta
from app.core.time import utc_now
from app.models.medication_use import MedicationUseRevision, MedicationReconciliation
from tests.test_hardening import admin_token as admin_token, grant, headers
from tests.test_prescriptions import setup_source, generate, save_payload

BASE = "/api/v1/clinical/medication-use"


def report(patient_id, **changes):
    data = dict(
        patient_id=patient_id,
        name="SYNTHETIC-A",
        dose=None,
        frequency=None,
        use_status="unknown",
        reported_on="2026-01-01",
        notes="Synthetic patient account",
        reason="Initial patient account for testing",
    )
    data.update(changes)
    return data


def review(**changes):
    data = dict(
        expected_report_version=1,
        expected_review_version=0,
        assessment="needs_clarification",
        note="Synthetic report needs source clarification",
        comparison_checked=True,
    )
    data.update(changes)
    return data


def create(client, token, patient_id, **changes):
    response = client.post(BASE, headers=headers(token), json=report(patient_id, **changes))
    assert response.status_code == 201, response.text
    return response.json()


def test_patient_reports_corrects_and_retains_history_without_promoting_to_prescription(
    client, patient_token, patient_user, db_session
):
    target = patient_user.patient_profile.id
    created = create(client, patient_token, target)
    assert created["provenance"] == "patient_reported" and created["latest_review"] is None
    assert created["dose"] is None and created["source"] is None
    correction = report(target, use_status="not_taking", reason="Corrected synthetic account")
    correction.pop("patient_id")
    correction["expected_version"] = 1
    changed = client.put(f"{BASE}/{created['id']}", headers=headers(patient_token), json=correction)
    assert changed.status_code == 200 and changed.json()["version"] == 2
    assert (
        client.put(f"{BASE}/{created['id']}", headers=headers(patient_token), json=correction).status_code
        == 409
    )
    history = client.get(f"{BASE}/{created['id']}/history", headers=headers(patient_token)).json()
    assert [(row["version"], row["use_status"]) for row in history] == [(2, "not_taking"), (1, "unknown")]
    assert client.get(f"/api/v1/medications?patient_id={target}", headers=headers(patient_token)).json() == []
    assert db_session.query(MedicationUseRevision).count() == 2


def test_clinician_reviews_are_versioned_and_report_corrections_make_them_stale(
    client,
    patient_token,
    doctor_token,
    patient_user,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    created = create(client, patient_token, target)
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    url = f"{BASE}/{created['id']}"
    assert (
        client.post(url + "/reconciliation", headers=headers(patient_token), json=review()).status_code == 403
    )
    assert (
        client.post(
            url + "/reconciliation", headers=headers(doctor_token), json=review(comparison_checked=False)
        ).status_code
        == 422
    )
    reviewed = client.post(url + "/reconciliation", headers=headers(doctor_token), json=review())
    assert reviewed.status_code == 201, reviewed.text
    assert reviewed.json()["report_version"] == 1
    assert (
        client.post(url + "/reconciliation", headers=headers(doctor_token), json=review()).status_code == 409
    )
    listed = client.get(BASE, params={"patient_id": target}, headers=headers(patient_token)).json()[0]
    assert not listed["review_stale"] and listed["review_version"] == 1
    correction = report(target, use_status="taking", dose="Patient reports one synthetic unit")
    correction.pop("patient_id")
    correction["expected_version"] = 1
    assert client.put(url, headers=headers(patient_token), json=correction).json()["review_stale"]
    assert (
        client.post(
            url + "/reconciliation", headers=headers(doctor_token), json=review(expected_review_version=1)
        ).status_code
        == 409
    )
    assert (
        client.post(
            url + "/reconciliation",
            headers=headers(doctor_token),
            json=review(expected_report_version=2, expected_review_version=1, assessment="account_reviewed"),
        ).status_code
        == 201
    )
    history = client.get(url + "/reconciliation/history", headers=headers(patient_token)).json()
    assert [row["report_version"] for row in history] == [2, 1]
    assert db_session.query(MedicationReconciliation).count() == 2


def test_source_comparison_preserves_historical_entry_and_flags_changed_sources(
    client,
    patient_token,
    second_patient_token,
    second_patient_user,
    doctor_token,
    patient_user,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    _, source_url = setup_source(client, patient_token, db_session)
    draft = generate(client, patient_token, source_url)
    confirmed = client.post(source_url, headers=headers(doctor_token), json=save_payload(draft, True))
    assert confirmed.status_code == 201
    entries_url = f"/api/v1/medications?patient_id={target}"
    entry = client.get(entries_url, headers=headers(patient_token)).json()[0]
    assert (
        client.post(
            BASE,
            headers=headers(second_patient_token),
            json=report(second_patient_user.patient_profile.id, source_entry_id=entry["id"]),
        ).status_code
        == 422
    )
    created = create(
        client, patient_token, target, source_entry_id=entry["id"], dose="Different synthetic patient report"
    )
    url = f"{BASE}/{created['id']}"
    assert created["source"]["dose"] != created["dose"]
    comparison = review(
        assessment="discrepancy",
        expected_source_review_version=created["source"]["current_source_review_version"],
        expected_prescription_version=created["source"]["current_prescription_version"],
    )
    reviewed = client.post(url + "/reconciliation", headers=headers(doctor_token), json=comparison)
    assert reviewed.status_code == 201
    snapshot = reviewed.json()["source_snapshot"]
    generate(client, patient_token, source_url, version=2)
    assert (
        client.post(
            url + "/reconciliation",
            headers=headers(doctor_token),
            json={**comparison, "expected_review_version": 1},
        ).status_code
        == 409
    )
    current = client.get(BASE, params={"patient_id": target}, headers=headers(patient_token)).json()[0]
    assert current["review_stale"] and current["source"]["draft_pending"]
    assert current["latest_review"]["source_snapshot"] == snapshot
    assert client.get(entries_url, headers=headers(patient_token)).json()[0]["dose"] == entry["dose"]


def test_wrong_patient_admin_document_only_readonly_and_revoked_access_fail_closed(
    client,
    patient_token,
    second_patient_token,
    doctor_token,
    admin_token,
    patient_user,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    created = create(client, patient_token, target)
    url = f"{BASE}/{created['id']}"

    def denied(token):
        for path in (BASE + f"?patient_id={target}", url + "/history", url + "/reconciliation/history"):
            assert client.get(path, headers=headers(token)).status_code == 403
        assert client.post(url + "/reconciliation", headers=headers(token), json=review()).status_code == 403

    for token in (second_patient_token, doctor_token, admin_token):
        denied(token)
        assert client.post(BASE, headers=headers(token), json=report(target)).status_code == 403
    grant(db_session, patient_user, doctor_user)
    denied(doctor_token)
    clinical = grant(db_session, patient_user, doctor_user, include_clinical_records=True)
    assert client.get(BASE, params={"patient_id": target}, headers=headers(doctor_token)).status_code == 200
    assert (
        client.post(url + "/reconciliation", headers=headers(doctor_token), json=review()).status_code == 403
    )
    assert client.post(BASE, headers=headers(doctor_token), json=report(target)).status_code == 403
    clinical.allow_clinical_write = True
    doctor_user.doctor_profile.verification_status = "pending"
    db_session.commit()
    denied(doctor_token)
    doctor_user.doctor_profile.verification_status = "verified"
    clinical.valid_until = utc_now() - timedelta(seconds=1)
    db_session.commit()
    denied(doctor_token)
    clinical.valid_until = utc_now() + timedelta(hours=1)
    clinical.is_revoked = True
    db_session.commit()
    denied(doctor_token)


def test_invalid_reports_and_wrong_patient_source_are_rejected(
    client, patient_token, second_patient_token, patient_user, second_patient_user
):
    target = patient_user.patient_profile.id
    for changes in (
        {"name": " "},
        {"use_status": "prescribed"},
        {"reported_on": "2999-01-01"},
        {"dose": ""},
        {"source_entry_id": "00000000-0000-0000-0000-000000000000"},
        {"verified": True},
    ):
        assert (
            client.post(BASE, headers=headers(patient_token), json=report(target, **changes)).status_code
            == 422
        )
    assert client.post(BASE, headers=headers(second_patient_token), json=report(target)).status_code == 403
    assert (
        client.get(
            BASE,
            params={"patient_id": second_patient_user.patient_profile.id},
            headers=headers(patient_token),
        ).status_code
        == 403
    )
