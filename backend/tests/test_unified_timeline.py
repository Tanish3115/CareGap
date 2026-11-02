from tests.test_hardening import admin_token as admin_token, grant, headers, upload
from tests.test_health_records import BASE, payload
from tests.test_clinical import create_encounter
from tests.test_medication_use import create as create_use
from tests.test_prescriptions import setup_source, generate, save_payload

URL = "/api/v1/clinical/unified-timeline"


def test_unified_timeline_includes_current_records_and_filters_before_paging(
    client, patient_token, patient_user
):
    target = patient_user.patient_profile.id
    auth = headers(patient_token)
    doc = upload(client, patient_token, clinical_date="2026-01-09").json()["document"]
    encounter = create_encounter(client, patient_token, target).json()
    _task = client.post(
        "/api/v1/clinical/follow-ups",
        headers=auth,
        json=dict(encounter_id=encounter["id"], title="Synthetic due follow-up", due_on="2026-01-11"),
    ).json()
    lab = client.post(
        BASE,
        headers=auth,
        json=payload(target, dict(kind="lab", test_name="Synthetic lab"), title="Synthetic lab"),
    ).json()
    care = client.post(
        BASE,
        headers=auth,
        json=payload(target, dict(kind="referral", due_on="2026-01-12"), title="Synthetic referral"),
    ).json()
    _use = create_use(client, patient_token, target, reported_on="2026-01-05")
    response = client.get(URL, headers=auth, params=dict(patient_id=target, date_to="2026-01-31"))
    assert response.status_code == 200, response.text
    entries = response.json()
    assert {row["kind"] for row in entries} == {
        "document",
        "encounter",
        "follow_up",
        "lab",
        "referral",
        "reported_medication_use",
    }
    assert [row["event_date"] for row in entries] == sorted(
        (row["event_date"] for row in entries), reverse=True
    )
    assert next(row for row in entries if row["id"] == care["id"])["date_basis"] == "due_date"
    assert next(row for row in entries if row["id"] == doc["id"])["document_id"] == doc["id"]
    page = client.get(URL, headers=auth, params=dict(patient_id=target, kind="lab", limit=1)).json()
    assert len(page) == 1 and page[0]["id"] == lab["id"]
    corrected = client.put(
        BASE + "/" + lab["id"],
        headers=auth,
        json=payload(
            data=dict(kind="lab", test_name="Corrected lab"), expected_version=1, title="Corrected lab"
        ),
    )
    assert corrected.status_code == 200
    current = client.get(URL, headers=auth, params=dict(patient_id=target, kind="lab")).json()
    assert len(current) == 1 and current[0]["version"] == 2 and current[0]["title"] == "Corrected lab"
    assert (
        client.get(
            URL, headers=auth, params=dict(patient_id=target, date_from="2026-02-01", date_to="2026-01-01")
        ).status_code
        == 422
    )


def test_timeline_never_exposes_unshared_kinds_metadata_or_sources(
    client,
    patient_token,
    doctor_token,
    second_patient_token,
    admin_token,
    patient_user,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    _secret = client.post(
        BASE,
        headers=headers(patient_token),
        json=payload(target, dict(kind="diagnosis", condition="PRIVATE diagnosis"), title="PRIVATE title"),
    ).json()
    shared = client.post(
        BASE,
        headers=headers(patient_token),
        json=payload(target, dict(kind="lab", test_name="Shared lab"), title="SHARED title"),
    ).json()
    scope = grant(
        db_session, patient_user, doctor_user, include_clinical_records=True, clinical_resources=["labs"]
    )
    auth = headers(doctor_token)
    response = client.get(URL, headers=auth, params=dict(patient_id=target, limit=1))
    assert response.status_code == 200, response.text
    assert [row["id"] for row in response.json()] == [shared["id"]]
    assert "PRIVATE" not in response.text
    assert client.get(URL, headers=auth, params=dict(patient_id=target, kind="diagnosis")).status_code == 403
    for token in (second_patient_token, admin_token):
        assert client.get(URL, headers=headers(token), params=dict(patient_id=target)).status_code == 403
    scope.is_revoked = True
    db_session.commit()
    assert client.get(URL, headers=auth, params=dict(patient_id=target)).status_code == 403


def test_medication_timeline_does_not_require_or_reveal_transcription_scope(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    doc, url = setup_source(client, patient_token, db_session)
    full = grant(
        db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True
    )
    draft = generate(client, patient_token, url)
    assert client.post(url, headers=headers(doctor_token), json=save_payload(draft, True)).status_code == 201
    full.is_revoked = True
    db_session.commit()
    grant(
        db_session,
        patient_user,
        doctor_user,
        include_clinical_records=True,
        clinical_resources=["medications"],
    )
    response = client.get(
        URL, headers=headers(doctor_token), params=dict(patient_id=target, kind="historical_prescription")
    )
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 2
    assert all(row["history_path"] is None and row["source_path"].startswith("/medications?") for row in rows)
    assert (
        client.get(
            rows[0]["source_path"].replace("/medications?", "/api/v1/medications?"),
            headers=headers(doctor_token),
        ).status_code
        == 200
    )
