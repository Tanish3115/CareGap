from datetime import timedelta
from uuid import uuid4

import pytest

from app.core.time import utc_now
from tests.test_consent import request_access
from tests.test_hardening import admin_token as admin_token, grant, headers


def test_patient_can_read_own_card_and_views_are_audited(client, patient_token, patient_user):
    patient = patient_user.patient_profile
    response = client.get(f"/api/v1/patients/{patient.id}/card", headers=headers(patient_token))
    assert response.status_code == 200
    assert response.json() == {
        "id": patient.id,
        "patient_code": patient.patient_code,
        "full_name": patient_user.full_name,
    }
    events = client.get("/api/v1/consent/audit", headers=headers(patient_token)).json()
    assert any(e["resource_type"] == "patient_card" and e["action"] == "VIEW_RECORD" for e in events)


def test_card_requires_authentication_and_patient_ownership(
    client, patient_user, second_patient_token, admin_token
):
    path = f"/api/v1/patients/{patient_user.patient_profile.id}/card"
    assert client.get(path).status_code == 401
    assert client.get(path, headers=headers(second_patient_token)).status_code == 403
    assert client.get(path, headers=headers(admin_token)).status_code == 403


def test_pending_access_request_does_not_reveal_patient_card(client, patient_user, doctor_token):
    patient_id = patient_user.patient_profile.id
    assert request_access(client, doctor_token, patient_id).status_code == 201
    for identifier in (patient_id, str(uuid4()), patient_user.patient_profile.patient_code):
        response = client.get(f"/api/v1/patients/{identifier}/card", headers=headers(doctor_token))
        assert response.status_code == 403
        assert "patient_code" not in response.json()


@pytest.mark.parametrize("scope", ["all", "prescriptions_only", "labs_only"])
def test_authorized_doctor_card_discloses_identity_only(
    client, doctor_token, doctor_user, patient_user, db_session, scope
):
    patient = patient_user.patient_profile
    grant(db_session, patient_user, doctor_user, scope=scope)
    response = client.get(f"/api/v1/patients/{patient.id}/card", headers=headers(doctor_token))
    assert response.status_code == 200
    assert response.json() == {
        "id": patient.id,
        "patient_code": patient.patient_code,
        "full_name": patient_user.full_name,
    }
    # A sharing grant does not imply access to contact, demographic or clinical details.
    assert (
        not {"date_of_birth", "blood_group", "emergency_contact", "email", "address", "abha_id"}
        & response.json().keys()
    )


@pytest.mark.parametrize("state", ["revoked", "expired", "future", "unverified", "rejected"])
def test_card_access_stops_when_consent_or_professional_verification_is_inactive(
    client, doctor_token, doctor_user, patient_user, db_session, state
):
    consent = grant(db_session, patient_user, doctor_user)
    if state == "revoked":
        consent.is_revoked = True
    elif state == "expired":
        consent.valid_until = utc_now() - timedelta(seconds=1)
    elif state == "future":
        consent.valid_from = utc_now() + timedelta(minutes=10)
    else:
        doctor_user.doctor_profile.verification_status = "pending" if state == "unverified" else "rejected"
    db_session.commit()
    response = client.get(
        f"/api/v1/patients/{patient_user.patient_profile.id}/card", headers=headers(doctor_token)
    )
    assert response.status_code == 403


def test_card_access_remains_patient_specific(
    client, doctor_token, doctor_user, patient_user, second_patient_user, db_session
):
    grant(db_session, patient_user, doctor_user)
    response = client.get(
        f"/api/v1/patients/{second_patient_user.patient_profile.id}/card", headers=headers(doctor_token)
    )
    assert response.status_code == 403
