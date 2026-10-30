"""Explicit local operational commands; never expose administrator provisioning publicly."""
import argparse
import getpass
from app.database import SessionLocal, engine
from app.models.user import User
from app.core.security import hash_password
from app.schemas.auth import UserRegister
from app.services.audit_service import audit_service


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["create-admin"])
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()
    password = getpass.getpass("Administrator password (12+ characters): ")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords differ")
    validated = UserRegister(email=args.email, full_name=args.name, password=password)
    with SessionLocal() as db:
        if db.query(User).filter_by(email=str(validated.email).lower()).first():
            raise SystemExit("Account already exists; refusing to change privileges")
        user = User(email=str(validated.email).lower(), full_name=args.name, role="admin", hashed_password=hash_password(password))
        db.add(user)
        db.flush()
        audit_service.log_event(db, "PROVISION_ADMIN", "user", actor_id=user.id, resource_id=user.id)
    print("Administrator created. No clinical-record privileges were granted.")


if __name__ == "__main__":
    main()
