from uuid import uuid4
from app.models.consent import ConsentGrant
from tests.test_hardening import headers, upload, admin_token


def request_access(client, doctor_token, patient_id, **overrides):
    payload = dict(patient_id=patient_id, purpose="Synthetic continuity review", scope="prescriptions_only", duration_hours=24)
    payload.update(overrides)
    return client.post("/api/v1/consent/requests", headers=headers(doctor_token), json=payload)


def test_full_consent_lifecycle_with_selected_records(client, patient_token, second_patient_token, doctor_token, patient_user):
    first = upload(client, patient_token).json()["document"]
    second = upload(client, patient_token).json()["document"]
    patient_id = patient_user.patient_profile.id
    response = request_access(client, doctor_token, patient_id)
    assert response.status_code == 201
    request_id = response.json()["id"]
    assert request_access(client, doctor_token, patient_id).status_code == 409
    assert client.post(f"/api/v1/consent/requests/{request_id}/decision", headers=headers(second_patient_token), json={"decision": "approve"}).status_code == 404
    assert client.get(f"/api/v1/documents/{first['id']}/download", headers=headers(doctor_token)).status_code == 403
    approval = client.post(f"/api/v1/consent/requests/{request_id}/decision", headers=headers(patient_token), json={"decision": "approve", "document_ids": [first["id"]]})
    assert approval.status_code == 200
    assert client.post(f"/api/v1/consent/requests/{request_id}/decision", headers=headers(patient_token), json={"decision": "approve"}).status_code == 409
    records = client.get(f"/api/v1/documents?patient_id={patient_id}", headers=headers(doctor_token))
    assert [d["id"] for d in records.json()] == [first["id"]]
    assert client.get(f"/api/v1/documents/{second['id']}/download", headers=headers(doctor_token)).status_code == 403
    assert client.get(f"/api/v1/documents/{first['id']}/download", headers=headers(doctor_token)).status_code == 200
    assert client.get("/api/v1/consent/patients", headers=headers(doctor_token)).json()[0]["id"] == patient_id
    grants = client.get("/api/v1/consent/grants", headers=headers(patient_token)).json()
    grant_id = grants[0]["id"]
    assert client.post(f"/api/v1/consent/grants/{grant_id}/revoke", headers=headers(second_patient_token)).status_code == 404
    assert client.post(f"/api/v1/consent/grants/{grant_id}/revoke", headers=headers(patient_token)).status_code == 204
    assert client.get(f"/api/v1/documents/{first['id']}/download", headers=headers(doctor_token)).status_code == 403
    events = client.get("/api/v1/consent/audit", headers=headers(patient_token)).json()
    assert {e["action"] for e in events} >= {"REQUEST_ACCESS", "GRANT_CONSENT", "REVOKE_CONSENT", "DOWNLOAD_DOCUMENT"}


def test_deny_creates_no_grant(client, patient_token, doctor_token, patient_user, db_session):
    response = request_access(client, doctor_token, patient_user.patient_profile.id)
    request_id = response.json()["id"]
    assert client.post(f"/api/v1/consent/requests/{request_id}/decision", headers=headers(patient_token), json={"decision": "deny"}).status_code == 200
    assert db_session.query(ConsentGrant).count() == 0


def test_cannot_approve_unowned_document(client, patient_token, second_patient_token, doctor_token, patient_user):
    other = upload(client, second_patient_token).json()["document"]
    item = request_access(client, doctor_token, patient_user.patient_profile.id).json()
    assert client.post(f"/api/v1/consent/requests/{item['id']}/decision", headers=headers(patient_token), json={"decision": "approve", "document_ids": [other["id"]]}).status_code == 422


def test_admin_verifies_doctor_without_record_access(client, admin_token, doctor_user, doctor_token, db_session):
    doctor_user.doctor_profile.verification_status = "pending"
    db_session.commit()
    assert client.get("/api/v1/consent/patients", headers=headers(doctor_token)).status_code == 403
    response = client.post(f"/api/v1/admin/doctors/{doctor_user.doctor_profile.id}/verification", headers=headers(admin_token), json={"status": "verified", "evidence_reference": "Synthetic test evidence only"})
    assert response.status_code == 200
    assert client.get("/api/v1/consent/patients", headers=headers(doctor_token)).status_code == 200
    assert client.get("/api/v1/admin/doctors", headers=headers(doctor_token)).status_code == 403
