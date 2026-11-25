"""Send a recovery email from the operator's authorized Gmail mailbox."""

import base64
import logging
from email import policy
from email.message import EmailMessage
from urllib.parse import quote

from httpx import Client, Response

from app.config import settings


def _google_value(response: Response, key: str, operation: str) -> str:
    # Google error bodies can include private account or message details.
    if not response.is_success:
        logging.getLogger(__name__).warning("Gmail %s returned HTTP %s", operation, response.status_code)
        response.raise_for_status()
    value = response.json().get(key)
    if not isinstance(value, str) or not value.strip():
        logging.getLogger(__name__).warning("Gmail %s response omitted %s", operation, key)
        raise ValueError("Incomplete Gmail response")
    return value


def send_gmail(message: EmailMessage) -> None:
    # Keep each offline grant and bearer token on its intended Google endpoint.
    with Client(timeout=10, follow_redirects=False) as google:
        grant = google.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "refresh_token",
                "client_id": settings.GMAIL_CLIENT_ID,
                "client_secret": settings.GMAIL_CLIENT_SECRET.get_secret_value(),
                "refresh_token": settings.GMAIL_REFRESH_TOKEN.get_secret_value(),
            },
        )
        access = _google_value(grant, "access_token", "authorization")

        raw = base64.urlsafe_b64encode(message.as_bytes(policy=policy.SMTPUTF8)).decode("ascii")
        # Address the configured mailbox explicitly so a grant for a different account cannot send as itself.
        mailbox = quote(str(settings.PASSWORD_RESET_FROM_EMAIL), safe="")
        sent = google.post(
            f"https://gmail.googleapis.com/gmail/v1/users/{mailbox}/messages/send",
            headers={"Authorization": f"Bearer {access}"},
            json={"raw": raw},
        )
        _google_value(sent, "id", "message submission")
