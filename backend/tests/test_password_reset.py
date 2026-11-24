import hashlib
import re
from datetime import timedelta
from email import policy
from email.parser import BytesParser

import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import Settings, settings
from app.core.security import verify_password
from app.core.time import utc_now
from app.models.audit import AuditLog
from app.models.password_reset import PasswordResetToken
from app.models.session import AuthSession
from app.models.user import User
from app.services.password_reset import (
    DELIVERY_UNAVAILABLE,
    INVALID_LINK,
    LOCAL_REQUEST_MESSAGE,
    REQUEST_MESSAGE,
    reset_password,
    send_reset_email,
)
from tests.test_hardening import admin_token as admin_token, headers

NEW_PASSWORD = "SyntheticRecovered123!"


@pytest.fixture(autouse=True)
def outbox(tmp_path, monkeypatch):
    directory = tmp_path / "private-mail"
    monkeypatch.setattr(settings, "PASSWORD_RESET_DELIVERY", "local")
    monkeypatch.setattr(settings, "PASSWORD_RESET_OUTBOX_DIR", str(directory))
    monkeypatch.setattr(settings, "PASSWORD_RESET_BASE_URL", "http://localhost:3000")
    return directory


def request_link(client, email):
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


def read_link(outbox):
    newest = max(outbox.glob("*.eml"), key=lambda path: path.stat().st_mtime_ns)
    message = BytesParser(policy=policy.default).parsebytes(newest.read_bytes())
    link = re.search(r"http://localhost:3000/reset-password#token=([A-Za-z0-9_-]{43})", message.get_content())
    assert link
    return link[1], message


def confirm(client, token, password=NEW_PASSWORD):
    return client.post("/api/v1/auth/reset-password", json={"token": token, "password": password})


def test_request_response_hides_account_existence_and_never_returns_reset_secrets(
    client, patient_user, second_patient_user, db_session, outbox
):
    second_patient_user.is_active = False
    db_session.commit()
    responses = [
        request_link(client, email)
        for email in (patient_user.email.upper(), "unknown@example.com", second_patient_user.email)
    ]
    assert [response.status_code for response in responses] == [202, 202, 202]
    assert all(
        response.json() == {"message": LOCAL_REQUEST_MESSAGE, "delivery": "local"} for response in responses
    )
    assert len(list(outbox.glob("*.eml"))) == 1
    token, message = read_link(outbox)
    assert message["To"] == patient_user.email
    stored = db_session.query(PasswordResetToken).one()
    assert stored.token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert stored.token_hash != token and stored.used_at is None
    assert timedelta(minutes=29) < stored.expires_at - utc_now() <= timedelta(minutes=30)
    assert token not in "".join(response.text for response in responses)
    assert all(token not in (event.details or "") for event in db_session.query(AuditLog))


def test_reset_changes_password_revokes_all_sessions_and_does_not_log_in_automatically(
    client, patient_token, second_patient_token, patient_user, db_session, outbox
):
    login = client.post(
        "/api/v1/auth/login", json={"email": patient_user.email, "password": "PatientSecure123!"}
    )
    second_session = login.json()["access_token"]
    assert request_link(client, patient_user.email).status_code == 202
    token, _ = read_link(outbox)
    response = confirm(client, token)
    assert response.status_code == 200
    assert "access_token" not in response.json()
    assert "caregap_session" not in client.cookies
    for old in (patient_token, second_session):
        assert client.get("/api/v1/auth/me", headers=headers(old)).status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers(second_patient_token)).status_code == 200
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": patient_user.email, "password": "PatientSecure123!"}
        ).status_code
        == 401
    )
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": patient_user.email, "password": NEW_PASSWORD}
        ).status_code
        == 200
    )
    assert confirm(client, token).status_code == 400
    db_session.expire_all()
    assert verify_password(NEW_PASSWORD, patient_user.hashed_password)
    assert db_session.query(PasswordResetToken).one().used_at is not None
    assert db_session.query(AuditLog).filter_by(action="PASSWORD_RESET_COMPLETED").count() == 1


@pytest.mark.parametrize("state", ["expired", "used", "inactive", "tampered"])
def test_invalid_links_cannot_change_the_password_or_revoke_sessions(
    client, patient_token, patient_user, db_session, outbox, state
):
    request_link(client, patient_user.email)
    token, _ = read_link(outbox)
    stored = db_session.query(PasswordResetToken).one()
    if state == "expired":
        stored.expires_at = utc_now() - timedelta(seconds=1)
    elif state == "used":
        stored.used_at = utc_now()
    elif state == "inactive":
        patient_user.is_active = False
    else:
        token = ("B" if token[0] == "A" else "A") + token[1:]
    db_session.commit()
    response = confirm(client, token)
    assert response.status_code == 400 and response.json() == {"detail": INVALID_LINK}
    db_session.expire_all()
    assert verify_password("PatientSecure123!", patient_user.hashed_password)
    assert db_session.query(AuthSession).filter_by(user_id=patient_user.id, revoked_at=None).count() == 1


@pytest.mark.parametrize("password", ["short", "x" * 73, "界" * 25])
def test_reset_password_policy_matches_registration_without_consuming_link(
    client, patient_user, db_session, outbox, password
):
    request_link(client, patient_user.email)
    token, _ = read_link(outbox)
    response = confirm(client, token, password)
    assert response.status_code == 422
    assert token not in response.text and password not in response.text
    assert db_session.query(PasswordResetToken).one().used_at is None
    assert confirm(client, token).status_code == 200


def test_request_cooldown_preserves_earlier_links_and_reset_invalidates_every_link(
    client, patient_user, db_session, outbox
):
    request_link(client, patient_user.email)
    first, _ = read_link(outbox)
    request_link(client, patient_user.email)
    assert len(list(outbox.glob("*.eml"))) == 1
    stored = db_session.query(PasswordResetToken).one()
    stored.created_at = utc_now() - timedelta(minutes=2)
    db_session.commit()
    request_link(client, patient_user.email)
    second, _ = read_link(outbox)
    assert first != second and len(list(outbox.glob("*.eml"))) == 2
    with Session(bind=db_session.get_bind()) as stale:
        stale_user = stale.get(User, patient_user.id)
        stale_link = stale.get(PasswordResetToken, hashlib.sha256(second.encode()).hexdigest())
        assert stale_user and stale_link and stale_link.used_at is None
        assert confirm(client, first).status_code == 200
        with pytest.raises(HTTPException) as failure:
            reset_password(stale, second, "SyntheticSecondReset123!")
        assert failure.value.status_code == 400
    db_session.expire_all()
    assert verify_password(NEW_PASSWORD, patient_user.hashed_password)
    assert db_session.query(PasswordResetToken).filter_by(used_at=None).count() == 0


def test_reset_link_uses_configured_origin_instead_of_request_host(client, patient_user, outbox):
    response = client.post(
        "/api/v1/auth/forgot-password",
        json={"email": patient_user.email},
        headers={"Host": "synthetic-attacker.invalid"},
    )
    assert response.status_code == 202
    _, message = read_link(outbox)
    assert "synthetic-attacker.invalid" not in message.get_content()


def test_delivery_failure_never_exposes_provider_details_or_leaves_a_valid_token(
    client, patient_user, db_session, monkeypatch, caplog
):
    def failed_delivery(*_):
        raise RuntimeError("PRIVATE SMTP credential and reset token")

    monkeypatch.setattr("app.services.password_reset.send_reset_email", failed_delivery)
    response = request_link(client, patient_user.email)
    assert response.status_code == 202 and response.json() == {
        "message": LOCAL_REQUEST_MESSAGE,
        "delivery": "local",
    }
    assert db_session.query(PasswordResetToken).one().used_at is not None
    assert "PRIVATE" not in caplog.text and "PRIVATE" not in response.text


def test_disabled_delivery_does_not_claim_an_email_was_sent(client, patient_user, monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_DELIVERY", "disabled")
    for email in (patient_user.email, "unknown@example.com"):
        response = request_link(client, email)
        assert response.status_code == 503 and response.json() == {"detail": DELIVERY_UNAVAILABLE}


def test_email_delivery_response_is_distinct_from_local_preview_without_disclosing_accounts(
    client, patient_user, monkeypatch
):
    delivered = []
    monkeypatch.setattr(settings, "PASSWORD_RESET_DELIVERY", "resend")
    monkeypatch.setattr(
        "app.services.password_reset.send_reset_email", lambda email, _: delivered.append(email)
    )
    for email in (patient_user.email, "unknown@example.com"):
        response = request_link(client, email)
        assert response.status_code == 202
        assert response.json() == {"message": REQUEST_MESSAGE, "delivery": "email"}
    assert delivered == [patient_user.email]


def test_deactivation_invalidates_previously_issued_links_even_after_reactivation(
    client, patient_user, admin_token, outbox
):
    request_link(client, patient_user.email)
    token, _ = read_link(outbox)
    for active in (False, True):
        response = client.put(
            f"/api/v1/admin/users/{patient_user.id}/activation",
            headers=headers(admin_token),
            json={"expected_active": not active, "active": active, "evidence": "Synthetic lifecycle test"},
        )
        assert response.status_code == 200
    assert confirm(client, token).status_code == 400


def test_password_recovery_endpoints_are_rate_limited(client, monkeypatch):
    from app.core.limiter import limiter

    monkeypatch.setattr(limiter, "enabled", True)
    limiter.reset()
    try:
        requests = [request_link(client, "unknown@example.com") for _ in range(6)]
        assert [response.status_code for response in requests] == [202] * 5 + [429]
        attempts = [confirm(client, "A" * 43) for _ in range(11)]
        assert [response.status_code for response in attempts] == [400] * 10 + [429]
    finally:
        limiter.reset()


@pytest.mark.parametrize("security", ["starttls", "tls"])
def test_smtp_delivery_uses_verified_tls_and_a_configured_sender(monkeypatch, security):
    calls = []

    class MailServer:
        def __init__(self, host, port, **options):
            calls.append(("connect", host, port, options))

        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def starttls(self, **options):
            calls.append(("starttls", options))

        def login(self, *_):
            calls.append(("login",))

        def send_message(self, message):
            assert message["From"] == "sender@example.com" and message["To"] == "recipient@example.com"
            calls.append(("send",))

    monkeypatch.setattr(settings, "PASSWORD_RESET_DELIVERY", "smtp")
    monkeypatch.setattr(settings, "SMTP_SECURITY", security)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(settings, "PASSWORD_RESET_FROM_EMAIL", "sender@example.com")
    monkeypatch.setattr(settings, "SMTP_USERNAME", "synthetic-sender")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", SecretStr("synthetic-smtp-test-password"))
    monkeypatch.setattr(
        f"app.services.password_reset.smtplib.{'SMTP_SSL' if security == 'tls' else 'SMTP'}", MailServer
    )
    send_reset_email("recipient@example.com", "A" * 43)
    assert calls[-2:] == [("login",), ("send",)]
    context = calls[0][3]["context"] if security == "tls" else calls[1][1]["context"]
    assert context.check_hostname and context.verify_mode.name == "CERT_REQUIRED"


def test_password_recovery_configuration_rejects_unsafe_production_delivery():
    common = {"SECRET_KEY": "synthetic-settings-key-long-enough-for-testing", "_env_file": None}
    with pytest.raises(ValueError, match="local password reset outbox"):
        Settings(**common, ENVIRONMENT="production", PASSWORD_RESET_DELIVERY="local")
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(
            **common,
            ENVIRONMENT="production",
            PASSWORD_RESET_DELIVERY="smtp",
            SMTP_HOST="smtp.example.com",
            PASSWORD_RESET_FROM_EMAIL="sender@example.com",
        )
    with pytest.raises(ValueError, match="frontend origin"):
        Settings(**common, PASSWORD_RESET_BASE_URL="https://caregap.example/#attacker")


def test_https_email_delivery_uses_fixed_provider_and_private_authorization(monkeypatch):
    import httpx

    def send(url, *, headers, json, timeout):
        assert url == "https://api.resend.com/emails"
        assert headers["Authorization"] == "Bearer synthetic-email-provider-key"
        assert json["from"] == "sender@example.com" and json["to"] == ["recipient@example.com"]
        assert "reset-password#token=" in json["text"] and timeout == 10
        return httpx.Response(200, json={"id": "synthetic-message"}, request=httpx.Request("POST", url))

    monkeypatch.setattr(settings, "PASSWORD_RESET_DELIVERY", "resend")
    monkeypatch.setattr(settings, "PASSWORD_RESET_FROM_EMAIL", "sender@example.com")
    monkeypatch.setattr(settings, "RESEND_API_KEY", SecretStr("synthetic-email-provider-key"))
    monkeypatch.setattr("app.services.password_reset.httpx.post", send)
    send_reset_email("recipient@example.com", "A" * 43)


@pytest.mark.parametrize("account", ["patient", "doctor", "admin"])
def test_recovery_preserves_role_and_existing_profile(
    client, patient_user, doctor_user, admin_token, db_session, outbox, account
):
    user = {
        "patient": patient_user,
        "doctor": doctor_user,
        "admin": db_session.query(User).filter_by(role="admin").one(),
    }[account]
    if account == "admin":
        # The shared admin fixture uses a reserved .test address, which public
        # EmailStr validation rejects. Use a valid synthetic recovery address.
        user.email = "synthetic-recovery-admin@example.com"
        db_session.commit()
    profile_id = (
        user.patient_profile.id
        if account == "patient"
        else user.doctor_profile.id
        if account == "doctor"
        else None
    )
    assert request_link(client, user.email).status_code == 202
    token, _ = read_link(outbox)
    assert confirm(client, token).status_code == 200
    db_session.expire_all()
    assert user.role == account and verify_password(NEW_PASSWORD, user.hashed_password)
    if account == "patient":
        assert user.patient_profile.id == profile_id
    elif account == "doctor":
        assert user.doctor_profile.id == profile_id and user.doctor_profile.verification_status == "verified"
