import re
from app.core.identifiers import new_patient_code
from app.models.patient import Patient
from tests.test_consent import request_access
from tests.test_hardening import headers, upload


def test_patient_code_returned_in_profiles(client, patient_token, patient_user):
    me = client.get("/api/v1/auth/me", headers=headers(patient_token)).json()
    profile = client.get("/api/v1/patients/me", headers=headers(patient_token)).json()
    assert re.fullmatch(r"CG-[1-9][0-9]{7}", me["patient"]["patient_code"])
    assert profile["patient_code"] == me["patient"]["patient_code"]
    assert me["patient"]["id"] == patient_user.patient_profile.id


def test_code_requests_resolve_original_patient_and_still_require_consent(client, patient_token, doctor_token, patient_user):
    doc = upload(client, patient_token).json()["document"]
    code = patient_user.patient_profile.patient_code
    # Whitespace/lowercase pasted codes are normalized without changing the target.
    response = request_access(client, doctor_token, f"  {code.lower()}  ")
    assert response.status_code == 201
    assert response.json()["patient_id"] == patient_user.patient_profile.id
    assert client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers(doctor_token)).status_code == 403
    # UUID and short-code requests refer to the same pending request.
    assert request_access(client, doctor_token, patient_user.patient_profile.id).status_code == 409


def test_duplicate_code_retried_without_losing_registration(client, patient_user, db_session, monkeypatch):
    import app.services.patient_service as service
    existing = patient_user.patient_profile.patient_code
    replacement = new_patient_code()
    while replacement == existing:
        replacement = new_patient_code()
    candidates = iter([existing, replacement])
    monkeypatch.setattr(service, "new_patient_code", lambda: next(candidates))
    response = client.post("/api/v1/auth/register", json={"email": "synthetic-code-retry@example.com", "password": "SyntheticCodeRetry123!", "full_name": "Synthetic Code Retry", "role": "patient"})
    assert response.status_code == 201
    created = db_session.query(Patient).filter_by(user_id=response.json()["id"]).one()
    assert created.patient_code == replacement
    assert patient_user.patient_profile.patient_code == existing


def test_invalid_and_unknown_codes_do_not_reveal_patient_details(client, doctor_token):
    assert request_access(client, doctor_token, "CG-123").status_code == 422
    response = request_access(client, doctor_token, "CG-99999999")
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to request access for this identifier"}
