# /// script
# requires-python = ">=3.10"
# dependencies = ["google-auth-oauthlib==1.5.0", "pydantic==2.14.2", "email-validator==2.3.0"]
# ///
"""Authorize the CareGap sender with Google and prepare its Render environment settings."""

import argparse
import json
import tempfile
from pathlib import Path

from configure_reset_email import delivery_settings, save_settings

SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"


def authorize(client_file, sender):
    from google_auth_oauthlib.flow import InstalledAppFlow

    try:
        client = json.loads(client_file.read_text(encoding="utf-8-sig"))["installed"]
        client_id, secret = client["client_id"], client["client_secret"]
        if not all(isinstance(value, str) and value.strip() for value in (client_id, secret)):
            raise ValueError
    except (KeyError, TypeError, ValueError, OSError):
        raise SystemExit("Choose the Desktop app client JSON downloaded from Google Auth Platform.") from None

    # Only the client ID and secret come from the file. The destinations are fixed.
    flow = InstalledAppFlow.from_client_config(
        {
            "installed": {
                "client_id": client_id,
                "client_secret": secret,
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=[SEND_SCOPE],
        autogenerate_code_verifier=True,
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        timeout_seconds=300,
        prompt="consent",
        login_hint=sender,
        authorization_prompt_message="Approve Gmail sending permission in the Google browser window.",
        success_message="Return to CareGap setup to finish.",
    )
    if not credentials.refresh_token or SEND_SCOPE not in (
        credentials.granted_scopes or credentials.scopes or []
    ):
        raise SystemExit(
            "Google did not grant offline Gmail sending permission. Run setup again and approve it."
        )
    return {
        "GMAIL_CLIENT_ID": client_id,
        "GMAIL_CLIENT_SECRET": secret,
        "GMAIL_REFRESH_TOKEN": credentials.refresh_token,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("client_json", type=Path, help="Path to your downloaded Desktop app client JSON")
    parser.add_argument(
        "--sender",
        default="admin.caregap@gmail.com",
        help="Sending mailbox (default: %(default)s)",
    )
    parser.add_argument(
        "--origin", default="https://caregap360.vercel.app", help="Public CareGap frontend origin"
    )
    args = parser.parse_args()
    try:
        values = delivery_settings("gmail", args.sender, args.origin)
    except ValueError:
        raise SystemExit("Enter a valid sender address and frontend origin.") from None
    if not values["PASSWORD_RESET_BASE_URL"].startswith("https://"):
        raise SystemExit("Use the HTTPS address of your hosted CareGap frontend.")
    try:
        values.update(authorize(args.client_json, values["PASSWORD_RESET_FROM_EMAIL"]))
    except Exception:
        # OAuth exceptions can contain the authorization code or callback URL.
        raise SystemExit(
            "Google authorization failed. Check the OAuth client, consent audience and Gmail access."
        ) from None

    with tempfile.NamedTemporaryFile(prefix="caregap-gmail-", suffix=".env", delete=False) as output:
        path = Path(output.name)
    try:
        save_settings(path, values)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    print(f"Google authorized Gmail sending. Your private Render settings are in {path}")
    print("In the CareGap backend on Render, import these six settings under Environment and deploy.")
    print("Remove the temporary file after importing it.")


if __name__ == "__main__":
    main()
