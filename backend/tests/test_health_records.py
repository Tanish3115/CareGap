import pytest
from tests.test_hardening import admin_token as admin_token, grant, headers, upload

BASE = "/api/v1/clinical/records"


def payload(patient_id=None, data=None, **changes):
    result = dict(
        title="Synthetic structured record",
        occurred_on="2026-01-01",
        data=data or dict(kind="diagnosis", condition="SYNTHETIC condition"),
        reason="Synthetic source and patient association checked",
        source_checked=True,
    )
    if patient_id:
        result["patient_id"] = patient_id
    result.update(changes)
    return result


@pytest.mark.parametrize(
    "data",
    [
        dict(kind="diagnosis", condition="SYNTHETIC condition"),
        dict(kind="allergy", substance="SYNTHETIC-A", reaction=None),
        dict(kind="lab", test_name="SYNTHETIC lab", value="unreadable"),
        dict(kind="appointment", due_on="2026-01-01"),
        dict(kind="referral", due_on="2026-01-01"),
        dict(kind="test", due_on="2026-01-01"),
    ],
)
def test_typed_records_keep_provenance_sources_and_versions(
    client, patient_token, patient_user, db_session, data
):
    source = upload(client, patient_token).json()["document"]
    created = client.post(
        BASE,
        headers=headers(patient_token),
        json=payload(patient_user.patient_profile.id, data, source_document_ids=[source["id"]]),
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["provenance"] == "patient_reported" and body["sources"][0]["id"] == source["id"]
    correction = payload(
        data=data, title="Corrected synthetic record", expected_version=1, source_document_ids=[]
    )
    response = client.put(f"{BASE}/{body['id']}", headers=headers(patient_token), json=correction)
    assert response.status_code == 200 and response.json()["version"] == 2
    assert (
        client.put(f"{BASE}/{body['id']}", headers=headers(patient_token), json=correction).status_code == 409
    )
    history = client.get(f"{BASE}/{body['id']}/history", headers=headers(patient_token)).json()
    assert [row["version"] for row in history] == [2, 1]
    assert history[1]["sources"] and not history[0]["sources"]


def test_clinician_only_resources_and_intervention_version_binding(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    care = client.post(
        BASE, headers=headers(patient_token), json=payload(target, dict(kind="referral", due_on="2026-01-01"))
    ).json()
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    for kind in ("medication_order", "dispensing", "confirmed_use"):
        data = dict(kind=kind, name="SYNTHETIC-A")
        assert (
            client.post(BASE, headers=headers(patient_token), json=payload(target, data)).status_code == 403
        )
        recorded = client.post(BASE, headers=headers(doctor_token), json=payload(target, data))
        assert recorded.status_code == 201, recorded.text
        assert recorded.json()["data"]["dose"] is None
    intervention = dict(kind="intervention", target_id=care["id"], target_version=1, action="staff_outreach")
    created = client.post(BASE, headers=headers(doctor_token), json=payload(target, intervention))
    assert created.status_code == 201, created.text
    assert (
        client.put(
            f"{BASE}/{care['id']}",
            headers=headers(patient_token),
            json=payload(
                data=dict(
                    kind="referral",
                    due_on="2026-01-01",
                    status="completed",
                    outcome="Synthetic attendance report",
                ),
                expected_version=1,
            ),
        ).status_code
        == 200
    )
    assert client.get(f"{BASE}/{created.json()['id']}", headers=headers(doctor_token)).json()[
        "linked_record_stale"
    ]
    assert (
        client.post(BASE, headers=headers(doctor_token), json=payload(target, intervention)).status_code
        == 409
    )


def test_invalid_fields_cross_patient_links_and_kind_changes_rejected(
    client,
    patient_token,
    second_patient_token,
    patient_user,
    second_patient_user,
    doctor_token,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    foreign = upload(client, second_patient_token).json()["document"]
    assert (
        client.post(
            BASE, headers=headers(patient_token), json=payload(target, source_document_ids=[foreign["id"]])
        ).status_code
        == 422
    )
    for data in (
        dict(kind="lab", test_name="SYNTHETIC", invented=True),
        dict(kind="diagnosis", condition="SYNTHETIC\x00invalid"),
        dict(kind="appointment", due_on="2026-01-01", status="completed"),
        dict(kind="medication_order", name="SYNTHETIC", start_on="2026-02-01", end_on="2026-01-01"),
        dict(kind="allergy", substance=" "),
    ):
        assert (
            client.post(BASE, headers=headers(patient_token), json=payload(target, data)).status_code == 422
        )
    created = client.post(BASE, headers=headers(patient_token), json=payload(target)).json()
    assert (
        client.put(
            f"{BASE}/{created['id']}",
            headers=headers(patient_token),
            json=payload(data=dict(kind="lab", test_name="SYNTHETIC"), expected_version=1),
        ).status_code
        == 422
    )
    foreign_care = client.post(
        BASE,
        headers=headers(second_patient_token),
        json=payload(second_patient_user.patient_profile.id, dict(kind="test", due_on="2026-01-01")),
    ).json()
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    assert (
        client.post(
            BASE,
            headers=headers(doctor_token),
            json=payload(
                target,
                dict(kind="intervention", target_id=foreign_care["id"], target_version=1, action="reminder"),
            ),
        ).status_code
        == 422
    )


def test_every_route_requires_clinical_consent_and_revocation_blocks_history(
    client,
    patient_token,
    second_patient_token,
    admin_token,
    doctor_token,
    patient_user,
    doctor_user,
    db_session,
):
    target = patient_user.patient_profile.id
    created = client.post(BASE, headers=headers(patient_token), json=payload(target)).json()
    url = f"{BASE}/{created['id']}"
    for token in (second_patient_token, admin_token, doctor_token):
        for path in (url, url + "/history", BASE + f"?patient_id={target}"):
            assert client.get(path, headers=headers(token)).status_code == 403
        assert client.put(url, headers=headers(token), json=payload(expected_version=1)).status_code == 403
    clinical = grant(db_session, patient_user, doctor_user, include_clinical_records=True)
    assert client.get(url, headers=headers(doctor_token)).status_code == 200
    assert client.put(url, headers=headers(doctor_token), json=payload(expected_version=1)).status_code == 403
    clinical.is_revoked = True
    db_session.commit()
    assert client.get(url + "/history", headers=headers(doctor_token)).status_code == 403


def test_rescheduling_requests_cannot_be_approved_by_patient(
    client, patient_token, doctor_token, patient_user, doctor_user, db_session
):
    target = patient_user.patient_profile.id
    data = dict(
        kind="appointment",
        due_on="2026-01-01",
        reschedule_requested_for="2026-01-02",
        reschedule_reason="Synthetic schedule request",
        reschedule_decision="requested",
    )
    created = client.post(BASE, headers=headers(patient_token), json=payload(target, data))
    assert created.status_code == 201, created.text
    decision = {
        **data,
        "due_on": "2026-01-02",
        "reschedule_decision": "approved",
        "reschedule_review_note": "Synthetic clinician schedule review",
    }
    url = BASE + "/" + created.json()["id"]
    assert (
        client.put(
            url, headers=headers(patient_token), json=payload(data=decision, expected_version=1)
        ).status_code
        == 403
    )
    grant(db_session, patient_user, doctor_user, include_clinical_records=True, allow_clinical_write=True)
    assert (
        client.put(
            url, headers=headers(doctor_token), json=payload(data=decision, expected_version=1)
        ).status_code
        == 200
    )
