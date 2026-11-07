"""Preview by default; explicit maintenance acknowledgement required to copy files."""

import argparse
from collections import Counter

from sqlalchemy import select

from app.database import SessionLocal
from app.models import *  # noqa: F403 -- register foreign-key models for operator ORM use
from app.models.document import MedicalDocument
from app.services.object_storage import S3PrivateObjectStore
from app.services.storage_migration import migrate_document
from app.services.storage_service import storage_service


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--writes-and-workers-stopped", action="store_true")
    arguments = parser.parse_args()
    if arguments.apply and not arguments.writes_and_workers_stopped:
        parser.error("Stop application writes and workers, then acknowledge maintenance mode")
    counts = Counter()
    remote = S3PrivateObjectStore()
    with SessionLocal() as db:
        ids = list(db.scalars(select(MedicalDocument.id).order_by(MedicalDocument.id)))
        db.rollback()
        for document_id in ids:
            try:
                status = migrate_document(db, document_id, storage_service, remote, apply=arguments.apply)
                if arguments.apply:
                    db.commit()
                else:
                    db.rollback()
                counts[status] += 1
            except Exception:
                db.rollback()
                # No paths, patient identifiers, provider responses or credentials in output.
                print(
                    "Migration stopped; current document unchanged. Preserve sources and investigate privately."
                )
                raise SystemExit(1) from None
    print("Migration summary:", dict(counts))


if __name__ == "__main__":
    main()
