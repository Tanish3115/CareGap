from app.models.audit import AuditLog
from app.models.clinical import Encounter, EncounterRevision, EncounterSource, FollowUpTask, FollowUpRevision
from tests.test_clinical import approve_clinical, create_encounter, encounter_payload
from tests.test_hardening import admin_token as admin_token, headers, upload


def test_patient_deletion_removes_all_revisions_and_tasks_but_retains_sources(
    client, patient_token, patient_user, db_session
):
    source = upload(client, patient_token).json()["document"]
    record = create_encounter(
        client, patient_token, patient_user.patient_profile.id, source_document_ids=[source["id"]]
    ).json()
    updated = client.put(
        f"/api/v1/clinical/encounters/{record['id']}",
        headers=headers(patient_token),
        json={
            **encounter_payload(source_document_ids=[source["id"]]),
            "expected_version": 1,
            "correction_reason": "Synthetic revision before deletion",
        },
    ).json()
    task = client.post(
        "/api/v1/clinical/follow-ups",
        headers=headers(patient_token),
        json={"encounter_id": record["id"], "title": "Synthetic task", "due_on": "2026-01-11"},
    ).json()
    response = client.delete(
        f"/api/v1/clinical/encounters/{record['id']}?expected_version={updated['version']}",
        headers=headers(patient_token),
    )
    assert response.status_code == 204, response.text
    for model in (Encounter, EncounterRevision, EncounterSource, FollowUpTask, FollowUpRevision):
        assert db_session.query(model).count() == 0
    assert (
        client.get(
            f"/api/v1/clinical/encounters/{record['id']}/history", headers=headers(patient_token)
        ).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/clinical/follow-ups/{task['id']}", headers=headers(patient_token)).status_code
        == 404
    )
    assert (
        client.get(f"/api/v1/documents/{source['id']}/download", headers=headers(patient_token)).status_code
        == 200
    )
    event = db_session.query(AuditLog).filter_by(action="DELETE_ENCOUNTER").one()
    assert event.resource_id == record["id"] and event.details is None


def test_only_owner_can_delete_even_with_clinical_write_consent(
    client, patient_token, second_patient_token, doctor_token, admin_token, patient_user
):
    record = create_encounter(client, patient_token, patient_user.patient_profile.id).json()
    approve_clinical(client, patient_token, doctor_token, patient_user.patient_profile.id, write=True)
    url = f"/api/v1/clinical/encounters/{record['id']}?expected_version=1"
    for token in (second_patient_token, doctor_token, admin_token):
        assert client.delete(url, headers=headers(token)).status_code == 403
    assert client.delete(url).status_code == 401
    assert (
        client.get(f"/api/v1/clinical/encounters/{record['id']}", headers=headers(patient_token)).status_code
        == 200
    )


def test_stale_deletion_is_rejected_and_removed_status_endpoint_stays_unavailable(
    client, patient_token, patient_user
):
    record = create_encounter(client, patient_token, patient_user.patient_profile.id).json()
    url = f"/api/v1/clinical/encounters/{record['id']}"
    assert (
        client.put(
            url,
            headers=headers(patient_token),
            json={
                **encounter_payload(),
                "expected_version": 1,
                "correction_reason": "Synthetic edit after deletion dialog opened",
            },
        ).status_code
        == 200
    )
    assert client.delete(url + "?expected_version=1", headers=headers(patient_token)).status_code == 409
    assert client.delete(url, headers=headers(patient_token)).status_code == 422
    assert (
        client.post(
            url + "/status", headers=headers(patient_token), json={"status": "entered_in_error"}
        ).status_code
        == 404
    )
    assert client.get(url, headers=headers(patient_token)).json()["version"] == 2
