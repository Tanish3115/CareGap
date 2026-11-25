import json
import re
from base64 import urlsafe_b64decode
from email import policy
from email.parser import BytesParser
from functools import partial
from urllib.parse import parse_qs

import httpx
import pytest
from pydantic import SecretStr

from app.config import Settings, settings
from app.models.audit import AuditLog
from app.models.password_reset import PasswordResetToken
from app.services import gmail_delivery

ORIGIN = "https://caregap.example.com"
SENDER = "sender+caregap@example.com"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/sender%2Bcaregap%40example.com/messages/send"
GMAIL = {
    "GMAIL_CLIENT_ID": "synthetic-client",
    "GMAIL_CLIENT_SECRET": "synthetic-client-secret",
    "GMAIL_REFRESH_TOKEN": "synthetic-refresh-token",
}


@pytest.fixture
def google_transport(monkeypatch):
    monkeypatch.setattr(settings, "PASSWORD_RESET_DELIVERY", "gmail")
    monkeypatch.setattr(settings, "PASSWORD_RESET_BASE_URL", ORIGIN)
    monkeypatch.setattr(settings, "PASSWORD_RESET_FROM_EMAIL", SENDER)
    monkeypatch.setattr(settings, "GMAIL_CLIENT_ID", GMAIL["GMAIL_CLIENT_ID"])
    for field in ("GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"):
        monkeypatch.setattr(settings, field, SecretStr(GMAIL[field]))

    def install(handler):
        monkeypatch.setattr(
            gmail_delivery, "Client", partial(httpx.Client, transport=httpx.MockTransport(handler))
        )

    return install


def test_gmail_message_from_forgot_password_to_login(
    client, db_session, patient_user, google_transport, monkeypatch
):
    monkeypatch.delenv("PASSWORD_RESET_FROM_EMAIL", raising=False)
    defaults = Settings(
        _env_file=None, SECRET_KEY="synthetic-test-key-long-enough-for-gmail", ENVIRONMENT="test"
    )
    monkeypatch.setattr(settings, "PASSWORD_RESET_FROM_EMAIL", defaults.PASSWORD_RESET_FROM_EMAIL)
    mailbox_url = "https://gmail.googleapis.com/gmail/v1/users/admin.caregap%40gmail.com/messages/send"
    calls, messages = [], []

    def google(request):
        calls.append(str(request.url))
        assert request.method == "POST"
        if str(request.url) == TOKEN_URL:
            assert "Authorization" not in request.headers
            assert parse_qs(request.content.decode()) == {
                "grant_type": ["refresh_token"],
                "client_id": [GMAIL["GMAIL_CLIENT_ID"]],
                "client_secret": [GMAIL["GMAIL_CLIENT_SECRET"]],
                "refresh_token": [GMAIL["GMAIL_REFRESH_TOKEN"]],
            }
            return httpx.Response(200, json={"access_token": "synthetic-access", "token_type": "Bearer"})
        assert (
            str(request.url) == mailbox_url and request.headers["Authorization"] == "Bearer synthetic-access"
        )
        payload = json.loads(request.content)
        assert set(payload) == {"raw"}
        messages.append(BytesParser(policy=policy.default).parsebytes(urlsafe_b64decode(payload["raw"])))
        return httpx.Response(200, json={"id": "synthetic-gmail-receipt"})

    google_transport(google)

    def request_link(address):
        return client.post("/api/v1/auth/forgot-password", json={"email": address})

    unknown = request_link("unregistered@example.com")
    assert not calls
    known = request_link(patient_user.email)
    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json() and known.json()["delivery"] == "email"
    assert calls == [TOKEN_URL, mailbox_url]
    (message,) = messages
    assert str(message["To"]) == patient_user.email and str(message["From"]) == "admin.caregap@gmail.com"
    assert message["Cc"] is None and message["Bcc"] is None
    assert message["Subject"] == "Reset your CareGap 360 password"
    plain = message.get_body(preferencelist=("plain",)).get_content()
    html = message.get_body(preferencelist=("html",)).get_content()
    link = re.search(r'href="([^"]+)"', html)[1]
    assert link in plain
    token = re.fullmatch(re.escape(ORIGIN) + r"/reset-password#token=([A-Za-z0-9_-]{43})", link)[1]
    receipt = db_session.query(AuditLog).filter_by(action="PASSWORD_RESET_EMAIL_ACCEPTED").one()
    assert receipt.details == "gmail" and token not in known.text

    password = "SyntheticGmailReset123!"
    payload = {"token": token, "password": password}
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 200
    assert client.post("/api/v1/auth/reset-password", json=payload).status_code == 400
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": patient_user.email, "password": password}
        ).status_code
        == 200
    )


@pytest.mark.parametrize(
    ("failure_url", "status", "response"),
    [
        (TOKEN_URL, 400, {"error": "invalid_grant", "error_description": "private-provider-details"}),
        (TOKEN_URL, 200, {"error": "missing token"}),
        (SEND_URL, 403, {"error": {"message": "private-provider-details"}}),
        (SEND_URL, 429, {"error": {"message": "private-provider-details"}}),
        (SEND_URL, 200, {}),
    ],
)
def test_google_failure_invalidates_link(
    client, patient_user, db_session, caplog, google_transport, failure_url, status, response
):
    calls = []

    def google(request):
        calls.append(str(request.url))
        if str(request.url) == failure_url:
            return httpx.Response(status, json=response)
        return httpx.Response(200, json={"access_token": "synthetic-access"})

    google_transport(google)
    result = client.post("/api/v1/auth/forgot-password", json={"email": patient_user.email})
    assert result.status_code == 202
    assert calls == ([TOKEN_URL] if failure_url == TOKEN_URL else [TOKEN_URL, SEND_URL])
    assert db_session.query(PasswordResetToken).one().used_at is not None
    actions = {row.action for row in db_session.query(AuditLog)}
    assert "PASSWORD_RESET_DELIVERY_FAILED" in actions and "PASSWORD_RESET_EMAIL_ACCEPTED" not in actions
    stage = "authorization" if failure_url == TOKEN_URL else "message submission"
    assert f"Gmail {stage}" in caplog.text
    assert all(
        private not in result.text + caplog.text
        for private in (
            "private-provider-details",
            GMAIL["GMAIL_CLIENT_SECRET"],
            GMAIL["GMAIL_REFRESH_TOKEN"],
        )
    )


@pytest.mark.parametrize("missing", [*GMAIL, "PASSWORD_RESET_FROM_EMAIL"])
def test_gmail_requires_a_sender_and_offline_grant(missing):
    values = {**GMAIL, "PASSWORD_RESET_FROM_EMAIL": SENDER, "PASSWORD_RESET_DELIVERY": "gmail"}
    values[missing] = ""
    with pytest.raises(ValueError):
        Settings(_env_file=None, SECRET_KEY="synthetic-test-key-long-enough-for-gmail", **values)


def test_production_gmail_requires_https_reset_links():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(
            _env_file=None,
            SECRET_KEY="synthetic-test-key-long-enough-for-gmail",
            ENVIRONMENT="production",
            PASSWORD_RESET_DELIVERY="gmail",
            PASSWORD_RESET_FROM_EMAIL=SENDER,
            PASSWORD_RESET_BASE_URL="http://caregap.example.com",
            **GMAIL,
        )
