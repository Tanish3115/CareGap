"""Synthetic migration failures must preserve both the source and database pointer."""

import pytest
from botocore.exceptions import ClientError

from app.models.document import MedicalDocument
from app.services.object_storage import S3PrivateObjectStore
from app.services.storage_migration import migrate_document
from app.services.storage_service import storage_service
from tests.test_hardening import upload
from tests.test_object_storage import MemoryS3


class ConditionalS3(MemoryS3):
    def put_object(self, **arguments):
        assert arguments["IfNoneMatch"] == "*"
        if (arguments["Bucket"], arguments["Key"]) in self.objects:
            raise ClientError({"Error": {"Code": "PreconditionFailed"}}, "PutObject")
        super().put_object(**arguments)


@pytest.mark.parametrize("existing", [None, "matching", "conflicting"])
def test_verified_resumable_copy(client, patient_token, db_session, existing):
    document_id = upload(client, patient_token).json()["document"]["id"]
    document = db_session.get(MedicalDocument, document_id)
    source = storage_service.resolve(document.file_path)
    original = source.read_bytes()
    original_updated_at = document.updated_at
    fake = ConditionalS3()
    remote = S3PrivateObjectStore(client=fake, bucket="synthetic")
    destination = (remote.bucket, document.file_path)
    if existing:
        fake.objects[destination] = original if existing == "matching" else b"conflicting"
    assert migrate_document(db_session, document_id, storage_service, remote) == "ready"
    assert len(fake.objects) == bool(existing)
    if existing == "conflicting":
        with pytest.raises(Exception, match="integrity"):
            migrate_document(db_session, document_id, storage_service, remote, apply=True)
        db_session.rollback()
        assert document.storage_backend == "local"
        assert fake.objects[destination] == b"conflicting"
    else:
        assert migrate_document(db_session, document_id, storage_service, remote, apply=True) == "migrated"
        db_session.commit()
        assert document.storage_backend == "s3"
        assert document.updated_at == original_updated_at
        assert fake.objects[destination] == original
        assert (
            migrate_document(db_session, document_id, storage_service, remote, apply=True) == "already_remote"
        )
    assert source.read_bytes() == original


@pytest.mark.parametrize("failure", ["checksum", "size", "namespace", "download"])
def test_invalid_sources_or_failed_download_never_switch_pointer(
    client, patient_token, db_session, monkeypatch, failure
):
    document_id = upload(client, patient_token).json()["document"]["id"]
    document = db_session.get(MedicalDocument, document_id)
    source = storage_service.resolve(document.file_path)
    if failure == "checksum":
        source.write_bytes(b"tampered")
    elif failure == "size":
        document.file_size += 1
    elif failure == "namespace":
        document.file_path = "00000000-0000-0000-0000-000000000000/source.pdf"
    db_session.commit()
    remote = S3PrivateObjectStore(client=ConditionalS3(), bucket="synthetic")
    if failure == "download":

        def fail(*args):
            raise RuntimeError("synthetic read failure")

        monkeypatch.setattr(remote, "materialize", fail)
    with pytest.raises(Exception):
        migrate_document(db_session, document_id, storage_service, remote, apply=True)
    db_session.rollback()
    assert document.storage_backend == "local"
    assert source.exists()


def test_uncommitted_switch_can_resume_after_rollback(client, patient_token, db_session):
    document_id = upload(client, patient_token).json()["document"]["id"]
    remote = S3PrivateObjectStore(client=ConditionalS3(), bucket="synthetic")
    assert migrate_document(db_session, document_id, storage_service, remote, apply=True) == "migrated"
    db_session.rollback()
    assert db_session.get(MedicalDocument, document_id).storage_backend == "local"
    assert migrate_document(db_session, document_id, storage_service, remote, apply=True) == "migrated"
    db_session.commit()
    assert len(remote.client.objects) == 1


def test_provider_without_conditional_upload_support_fails_closed(client, patient_token, db_session):
    document_id = upload(client, patient_token).json()["document"]["id"]

    class Unsupported(ConditionalS3):
        def put_object(self, **arguments):
            raise ClientError({"Error": {"Code": "NotImplemented"}}, "PutObject")

    remote = S3PrivateObjectStore(client=Unsupported(), bucket="synthetic")
    with pytest.raises(Exception, match="upload failed"):
        migrate_document(db_session, document_id, storage_service, remote, apply=True)
    db_session.rollback()
    assert db_session.get(MedicalDocument, document_id).storage_backend == "local"
