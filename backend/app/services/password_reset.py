"""Password recovery through a private side channel, never through an API response."""

import hashlib
import logging
import os
import secrets
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage
from html import escape
from pathlib import Path
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import hash_password
from app.core.time import utc_now
from app.models.password_reset import PasswordResetToken
from app.models.session import AuthSession
from app.models.user import User
from app.services.audit_service import audit_service
from app.services.gmail_delivery import send_gmail

REQUEST_MESSAGE = "If an active account exists for this email, a password reset link will be sent."
LOCAL_REQUEST_MESSAGE = "If an active account exists for this email, its reset message will be saved locally. This development app does not send email."
INVALID_LINK = "This password reset link is invalid or has expired. Please request a new link."
DELIVERY_UNAVAILABLE = "Password recovery is unavailable. Please contact the service administrator."


def delivery_mode():
    return settings.PASSWORD_RESET_DELIVERY or (
        "disabled" if settings.ENVIRONMENT == "production" or settings.DEMO_MODE else "local"
    )


def token_digest(token):
    return hashlib.sha256(token.encode("ascii")).hexdigest()


def send_reset_email(recipient, token):
    # Use the configured origin, never the incoming Host or Origin headers.
    link = f"{settings.PASSWORD_RESET_BASE_URL.rstrip('/')}/reset-password#token={token}"
    message = EmailMessage()
    message["Subject"] = "Reset your CareGap 360 password"
    message["From"] = str(settings.PASSWORD_RESET_FROM_EMAIL or "no-reply@caregap.local")
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your CareGap 360 account.\n\n"
        f"Choose a new password using this link:\n{link}\n\n"
        f"This link expires in {settings.PASSWORD_RESET_TOKEN_MINUTES} minutes and works once.\n"
        "If you did not request this, ignore this email. Your password has not changed.\n",
        cte="7bit",
    )
    mode = delivery_mode()
    if mode == "gmail":
        message.add_alternative(
            "<p>A password reset was requested for your CareGap 360 account.</p>"
            f'<p><a href="{escape(link, quote=True)}">Reset your CareGap 360 password</a></p>'
            f"<p>This link works once and expires in {settings.PASSWORD_RESET_TOKEN_MINUTES} minutes.</p>"
            "<p>If you didn't request this change, you can ignore this email.</p>",
            subtype="html",
        )
        send_gmail(message)
        return
    if mode == "local" and settings.ENVIRONMENT != "production":
        outbox = Path(settings.PASSWORD_RESET_OUTBOX_DIR)
        outbox.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(outbox / f"{uuid4()}.eml", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(message.as_bytes())
        return
    if mode == "resend":
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY.get_secret_value()}"},
            json={
                "from": str(message["From"]),
                "to": [recipient],
                "subject": str(message["Subject"]),
                "text": message.get_content(),
            },
            timeout=10,
        )
        response.raise_for_status()
        return
    if mode != "smtp":
        raise RuntimeError("Password recovery delivery disabled")
    context = ssl.create_default_context()
    factory = smtplib.SMTP_SSL if settings.SMTP_SECURITY == "tls" else smtplib.SMTP
    options = {"timeout": 10}
    if settings.SMTP_SECURITY == "tls":
        options["context"] = context
    with factory(settings.SMTP_HOST, settings.SMTP_PORT, **options) as smtp:
        if settings.SMTP_SECURITY == "starttls":
            smtp.starttls(context=context)
        if settings.SMTP_USERNAME:
            smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD.get_secret_value())
        smtp.send_message(message)


def deliver_password_reset(email, bind):
    # This entire job runs after the generic response so account lookup and mail
    # delivery do not expose account existence through request timing.
    try:
        with Session(bind=bind) as db:
            user = db.query(User).filter(User.email == email, User.is_active.is_(True)).first()
            if not user:
                return
            # Serialize issuance with resets/deactivation and the per-account cooldown.
            locked = db.execute(
                update(User)
                .where(
                    User.id == user.id, User.is_active.is_(True), User.hashed_password == user.hashed_password
                )
                .values(updated_at=User.updated_at)
                .execution_options(synchronize_session=False)
            )
            if locked.rowcount != 1:
                return
            now = utc_now()
            # Bound repeated email delivery without locking or changing the account.
            if (
                db.query(PasswordResetToken)
                .filter(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.created_at > now - timedelta(minutes=1),
                )
                .first()
            ):
                return
            token = secrets.token_urlsafe(32)
            digest = token_digest(token)
            user_id, recipient = user.id, user.email
            db.add(
                PasswordResetToken(
                    token_hash=digest,
                    user_id=user_id,
                    created_at=now,
                    expires_at=now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_MINUTES),
                )
            )
            audit_service.log_event(db, "PASSWORD_RESET_REQUESTED", "auth", actor_id=user_id, commit=False)
            db.commit()
            try:
                send_reset_email(recipient, token)
            except Exception:
                db.execute(
                    update(PasswordResetToken)
                    .where(PasswordResetToken.token_hash == digest)
                    .values(used_at=utc_now())
                )
                audit_service.log_event(
                    db, "PASSWORD_RESET_DELIVERY_FAILED", "auth", actor_id=user_id, commit=False
                )
                db.commit()
                raise
            if delivery_mode() == "gmail":
                audit_service.log_event(
                    db, "PASSWORD_RESET_EMAIL_ACCEPTED", "auth", actor_id=user_id, details="gmail"
                )
    except Exception:
        # Provider errors can contain credentials, recipient addresses or URLs.
        logging.getLogger("caregap.password_reset").error("Password reset request could not be completed")


def reset_password(db, token, password):
    now = utc_now()
    digest = token_digest(token)
    reset = db.get(PasswordResetToken, digest)
    if not reset or reset.used_at is not None or reset.expires_at <= now:
        raise HTTPException(400, INVALID_LINK)
    user = db.get(User, reset.user_id)
    if not user or not user.is_active:
        raise HTTPException(400, INVALID_LINK)
    new_hash = hash_password(password)
    now = utc_now()

    # Serialize concurrent resets on the user row, with a compare-and-swap that
    # also works on SQLite. All following writes commit or roll back together.
    changed = db.execute(
        update(User)
        .where(User.id == user.id, User.is_active.is_(True), User.hashed_password == user.hashed_password)
        .values(hashed_password=new_hash, updated_at=now)
        .execution_options(synchronize_session=False)
    )
    claimed = db.execute(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == digest,
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
    )
    if changed.rowcount != 1 or claimed.rowcount != 1:
        db.rollback()
        raise HTTPException(400, INVALID_LINK)
    db.execute(
        update(PasswordResetToken)
        .where(PasswordResetToken.user_id == user.id, PasswordResetToken.used_at.is_(None))
        .values(used_at=now)
    )
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    audit_service.log_event(db, "PASSWORD_RESET_COMPLETED", "auth", actor_id=user.id, commit=False)
    db.commit()
