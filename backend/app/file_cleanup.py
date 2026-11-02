"""Idempotent file cleanup. The OCR worker retains its read-only vault mount."""

import argparse
import signal
import os
from datetime import timedelta
from threading import Event
from sqlalchemy.exc import SQLAlchemyError
from app.core.time import utc_now
from app.database import SessionLocal
from app.models.file_deletion import FileDeletion
from app.models.document import MedicalDocument
from app.services.storage_service import storage_service
from app.services.privacy_erasure import local_path


def run_one(session_factory=SessionLocal):
    with session_factory() as db:
        item = (
            db.query(FileDeletion)
            .filter(FileDeletion.status == "pending", FileDeletion.next_attempt_at <= utc_now())
            .order_by(FileDeletion.created_at, FileDeletion.id)
            .with_for_update(skip_locked=True)
            .first()
        )
        if item is None:
            return False
        item.attempts += 1
        try:
            if not item.storage_key.startswith(item.patient_id + "/"):
                raise ValueError("Invalid namespace")
            if (
                db.query(MedicalDocument)
                .filter_by(file_path=item.storage_key, storage_backend=item.storage_backend)
                .first()
            ):
                raise ValueError("Source still referenced")
            if item.storage_backend == "local":
                path = local_path(item.storage_key, item.patient_id)
                for other in db.query(MedicalDocument).filter_by(storage_backend="local").all():
                    other_path = storage_service.resolve(other.file_path)
                    if os.path.normcase(str(other_path)) == os.path.normcase(str(path)) or (
                        path.exists() and other_path.exists() and path.samefile(other_path)
                    ):
                        raise ValueError("Source still referenced")
                if path.exists():
                    storage_service.get_secure_file_path(item.storage_key, item.sha256)
            else:
                # A missing object is already clean. S3 deletion itself is idempotent.
                if item.storage_backend != "s3":
                    raise ValueError("Invalid backend")
            storage_service.delete_file(item.storage_key, backend=item.storage_backend)
            item.status, item.error_code = "done", None
            # Completed receipts retain no private object key or checksum.
            item.storage_key, item.sha256 = "", ""
        except Exception:
            item.error_code = "cleanup_requires_retry"
            item.next_attempt_at = utc_now() + timedelta(seconds=30)
        db.commit()
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.once:
        run_one()
        return
    stopping = Event()
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda *_: stopping.set())
    while not stopping.is_set():
        try:
            if run_one():
                continue
        except SQLAlchemyError:
            print("File cleanup database unavailable; retrying", flush=True)
        stopping.wait(2)


if __name__ == "__main__":
    main()
