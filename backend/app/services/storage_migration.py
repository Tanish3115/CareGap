"""Operator-only, resumable local-to-private-object migration. Never deletes sources."""

from uuid import UUID

from sqlalchemy import select, update

from app.core.errors import InvalidFileException
from app.models.document import MedicalDocument
from app.services.object_storage import validate_key


def migrate_document(db, document_id, local, remote, *, apply=False):
    """Caller must stop application writes/workers and commit each completed document.

    Conditional creation prevents overwriting another object. After an interrupted
    upload/commit, an existing object is reusable only after a full verified read.
    """
    document = db.scalar(select(MedicalDocument).where(MedicalDocument.id == document_id).with_for_update())
    if document is None:
        raise InvalidFileException("Migration document is unavailable")
    key = validate_key(document.file_path)
    if key.split("/")[0] != str(UUID(document.patient_id)) or len(key.split("/")) != 2:
        raise InvalidFileException("Migration patient namespace mismatch")
    if document.storage_backend == "s3":
        with remote.materialize(key, document.sha256_hash) as source:
            if source.stat().st_size != document.file_size:
                raise InvalidFileException("Migration size mismatch")
        return "already_remote"
    if document.storage_backend != "local":
        raise InvalidFileException("Unknown migration source")
    with local.materialize(key, document.sha256_hash) as source:
        if source.stat().st_size != document.file_size:
            raise InvalidFileException("Migration size mismatch")
        if not apply:
            return "ready"
        # Reuse the store's encryption configuration while requiring atomic creation.
        remote.put_file_if_absent(key, source, document.sha256_hash, document.mime_type)
        with remote.materialize(key, document.sha256_hash) as downloaded:
            if downloaded.stat().st_size != document.file_size:
                raise InvalidFileException("Migration size mismatch")
        result = db.execute(
            update(MedicalDocument)
            .where(
                MedicalDocument.id == document.id,
                MedicalDocument.storage_backend == "local",
                MedicalDocument.file_path == key,
                MedicalDocument.sha256_hash == document.sha256_hash,
            )
            .values(storage_backend="s3", updated_at=document.updated_at)
        )
        if result.rowcount != 1:
            raise InvalidFileException("Migration source changed")
    return "migrated"
