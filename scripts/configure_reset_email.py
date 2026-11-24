"""Configure local Resend delivery through a masked, interactive key prompt."""

import getpass
import json
import os
import secrets
import sys
import warnings
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from pydantic import EmailStr, HttpUrl, TypeAdapter

ROOT = Path(__file__).resolve().parents[1]


def email_settings(api_key, sender, origin):
    key = api_key.strip()
    if (
        not key.startswith("re_")
        or len(key) < 12
        or not all(character.isascii() and (character.isalnum() or character in "_-") for character in key)
    ):
        raise ValueError("Enter a complete Resend API key. No settings were changed.")
    address = str(TypeAdapter(EmailStr).validate_python(sender.strip()))
    normalized = str(TypeAdapter(HttpUrl).validate_python(origin.strip()))
    parsed = urlsplit(normalized)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != "/":
        raise ValueError("Enter only the frontend origin, without a path or credentials.")
    return {
        "PASSWORD_RESET_DELIVERY": "resend",
        "PASSWORD_RESET_BASE_URL": normalized.rstrip("/"),
        "PASSWORD_RESET_FROM_EMAIL": address,
        "RESEND_API_KEY": key,
    }


def save_settings(path, values):
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise ValueError("An existing regular backend .env file is required.")
    original = path.read_bytes().decode("utf-8-sig")
    newline = "\r\n" if "\r\n" in original else "\n"
    result = []
    written = set()
    for line in original.splitlines():
        key = line.partition("=")[0].strip().removeprefix("export ")
        if key not in values or line.lstrip().startswith("#"):
            result.append(line)
        elif key not in written:
            result.append(f"{key}={json.dumps(values[key])}")
            written.add(key)
    for key, value in values.items():
        if key not in written:
            result.append(f"{key}={json.dumps(value)}")
    temporary = path.with_name(path.name + "." + secrets.token_hex(8) + ".tmp")
    try:
        descriptor = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(newline.join(result) + newline)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main():
    if not sys.stdin.isatty():
        raise SystemExit(
            "Run this setup in an interactive local terminal; keys must not be passed as arguments."
        )
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import settings

    if settings.ENVIRONMENT != "development":
        raise SystemExit(
            "This helper is for local development. Use your host's secret settings in production."
        )
    print("CareGap 360 - inbox email setup")
    print("1. Open https://resend.com/api-keys and sign in/create your account.")
    print("2. Create a key with email-sending access.")
    print("The test sender can deliver only to the email associated with your Resend account.")
    print("Your key will be saved only in backend/.env. It is never printed or sent to chat.")
    sender = input("Sender email [onboarding@resend.dev]: ").strip() or "onboarding@resend.dev"
    origin = (
        input(f"Frontend URL [{settings.PASSWORD_RESET_BASE_URL}]: ").strip()
        or settings.PASSWORD_RESET_BASE_URL
    )
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            key = getpass.getpass("Resend API key (hidden): ")
        values = email_settings(key, sender, origin)
        save_settings(ROOT / "backend" / ".env", values)
        state = ROOT / ".tools" / "runtime" / "reset-email-setup.json"
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(
            json.dumps(
                {
                    "configured": True,
                    "delivery": "resend",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            ),
            encoding="utf-8",
        )
    except (EOFError, KeyboardInterrupt, getpass.GetPassWarning):
        print("\nSetup cancelled. No email delivery was enabled.")
        return
    except (ValueError, OSError):
        print("Setup could not save valid settings. Check the key, sender and frontend URL, then retry.")
        return
    print("Email settings saved. Return to Codex to restart the API and test a real reset email.")
    input("Press Enter to close this window.")


if __name__ == "__main__":
    main()
