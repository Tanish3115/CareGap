import re
import pytest
from app.core.identifiers import new_patient_code
from app.models.patient import Patient
from app.models.user import User
from tests.test_consent import request_access
from tests.test_hardening import headers, upload


def test_patient_code_returned_in_profiles(client, patient_token, patient_user):
    me = client.get("/api/v1/auth/me", headers=headers(patient_token)).json()
    profile = client.get("/api/v1/patients/me", headers=headers(patient_token)).json()
    assert re.fullmatch(r"[A-Z][0-9]{3}", me["patient"]["patient_code"])
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
    response = request_access(client, doctor_token, "Z999")
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to request access for this identifier"}


@pytest.mark.parametrize("index,code", [(0, "A000"), (999, "A999"), (1000, "B000"), (25999, "Z999")])
def test_code_generator_includes_leading_zeroes_and_namespace_boundaries(monkeypatch, index, code):
    monkeypatch.setattr("app.core.identifiers.secrets.randbelow", lambda limit: index)
    assert new_patient_code() == code


def test_allocator_finds_free_code_after_repeated_random_collisions(client, patient_user, db_session, monkeypatch):
    import app.services.patient_service as service
    monkeypatch.setattr(service, "new_patient_code", lambda: patient_user.patient_profile.patient_code)
    response = client.post("/api/v1/auth/register", json={"email": "synthetic-fallback@example.com", "password": "SyntheticFallback123!", "full_name": "Synthetic Fallback", "role": "patient"})
    assert response.status_code == 201
    assert db_session.query(Patient).filter_by(user_id=response.json()["id"]).one().patient_code == "A000"


def test_namespace_exhaustion_rejects_registration_without_partial_account(client, patient_user, second_patient_user, db_session, monkeypatch):
    import app.services.patient_service as service
    # Exercise the real finite-namespace fallback with a two-slot test namespace.
    patient_user.patient_profile.patient_code = "A000"
    db_session.flush()
    second_patient_user.patient_profile.patient_code = "A001"
    db_session.commit()
    monkeypatch.setattr(service, "new_patient_code", lambda: "A000")
    monkeypatch.setattr(service, "PATIENT_CODE_CAPACITY", 2)
    response = client.post("/api/v1/auth/register", json={"email": "synthetic-capacity@example.com", "password": "SyntheticCapacity123!", "full_name": "Synthetic Capacity", "role": "patient"})
    assert response.status_code == 503
    assert "capacity" in response.json()["detail"].lower()
    assert db_session.query(User).filter_by(email="synthetic-capacity@example.com").first() is None
    assert db_session.query(Patient).count() == 2
