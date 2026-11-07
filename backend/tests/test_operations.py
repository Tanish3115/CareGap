from tests.test_hardening import admin_token as admin_token, headers
from app.models.user import User
from app.models.session import AuthSession


def test_verified_organization_scopes_grant_and_membership_loss_blocks_every_future_read(
    client, admin_token, doctor_token, patient_token, patient_user, doctor_user, db_session
):
    ah = headers(admin_token)
    dh = headers(doctor_token)
    ph = headers(patient_token)
    created = client.post(
        "/api/v1/admin/organizations",
        headers=ah,
        json=dict(
            name="Synthetic institution",
            status="verified",
            expected_version=0,
            evidence="Synthetic institutional evidence",
        ),
    )
    assert created.status_code == 201, created.text
    org = created.json()
    body = dict(
        patient_id=patient_user.patient_profile.id,
        organization_id=org["id"],
        scope="all",
        purpose="Synthetic organization continuity",
        include_clinical_records=True,
    )
    assert client.post("/api/v1/consent/requests", headers=dh, json=body).status_code == 403
    member = dict(
        user_id=doctor_user.id,
        role="clinician",
        status="active",
        expected_version=0,
        evidence="Synthetic employment verification",
    )
    assert (
        client.put(f"/api/v1/admin/organizations/{org['id']}/members", headers=ah, json=member).status_code
        == 200
    )
    requested = client.post("/api/v1/consent/requests", headers=dh, json=body)
    assert requested.status_code == 201 and requested.json()["organization_verified"]
    assert (
        client.post(
            f"/api/v1/consent/requests/{requested.json()['id']}/decision",
            headers=ph,
            json=dict(decision="approve"),
        ).status_code
        == 200
    )
    url = f"/api/v1/clinical/records?patient_id={patient_user.patient_profile.id}"
    assert client.get(url, headers=dh).status_code == 200
    assert (
        client.put(
            f"/api/v1/admin/organizations/{org['id']}/members",
            headers=ah,
            json={**member, "expected_version": 1, "status": "inactive"},
        ).status_code
        == 200
    )
    assert client.get(url, headers=dh).status_code == 403
    assert client.get("/api/v1/organizations/mine", headers=dh).json() == []
    for path in ("/admin/organizations", "/admin/users", "/admin/metrics", "/admin/privacy-requests"):
        assert client.get("/api/v1" + path, headers=ph).status_code == 403
        assert client.get("/api/v1" + path, headers=dh).status_code == 403


def test_account_deactivation_revokes_sessions_and_admins_cannot_self_deactivate(
    client, admin_token, patient_token, patient_user, db_session
):
    body = dict(expected_active=True, active=False, evidence="Synthetic account lifecycle review")
    result = client.put(
        f"/api/v1/admin/users/{patient_user.id}/activation", headers=headers(admin_token), json=body
    )
    assert result.status_code == 200 and result.json()["sessions_revoked"]
    assert client.get("/api/v1/auth/me", headers=headers(patient_token)).status_code == 401
    assert all(row.revoked_at for row in db_session.query(AuthSession).filter_by(user_id=patient_user.id))
    admin = db_session.query(User).filter_by(role="admin").one()
    assert (
        client.put(
            f"/api/v1/admin/users/{admin.id}/activation", headers=headers(admin_token), json=body
        ).status_code
        == 403
    )


def test_privacy_requests_and_personal_export_do_not_expose_secrets_or_foreign_records(
    client, patient_token, second_patient_token, admin_token, patient_user
):
    created = client.post(
        "/api/v1/privacy/requests", headers=headers(patient_token), json=dict(kind="erasure")
    )
    assert created.status_code == 201 and created.json()["status"] == "requested"
    assert client.get("/api/v1/privacy/requests", headers=headers(second_patient_token)).json() == []
    exported = client.get("/api/v1/privacy/export", headers=headers(patient_token))
    assert exported.status_code == 200 and exported.json()["profile"]["user_id"] == patient_user.id
    assert "hashed_password" not in exported.text and "caregap_session" not in exported.text
    assert client.get("/api/v1/privacy/export", headers=headers(admin_token)).status_code == 403
    request = created.json()
    reviewed = client.put(
        f"/api/v1/admin/privacy-requests/{request['id']}",
        headers=headers(admin_token),
        json=dict(
            expected_version=1,
            status="under_review",
            decision_reference="Synthetic retention policy review needed",
        ),
    )
    assert reviewed.status_code == 200 and reviewed.json()["version"] == 2
