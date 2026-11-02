import io
import hashlib
import pytest
from app.config import settings
from app.config import Settings
from app.models.document import MedicalDocument
from app.services.object_storage import S3PrivateObjectStore
from app.services.storage_service import storage_service
from tests.test_hardening import headers, upload
from tests.helpers import pdf_bytes


class MemoryS3:
    """Unit-test double only; actual MinIO round-trips have a separate integration suite."""

    def __init__(self):
        self.objects = {}

    def put_object(self, **arguments):
        assert "ACL" not in arguments
        self.objects[(arguments["Bucket"], arguments["Key"])] = arguments["Body"].read()

    def get_object(self, **arguments):
        content = self.objects[(arguments["Bucket"], arguments["Key"])]
        return {"Body": io.BytesIO(content), "ContentLength": len(content)}

    def delete_object(self, **arguments):
        self.objects.pop((arguments["Bucket"], arguments["Key"]), None)


def test_s3_materialization_checks_integrity_and_cleans_private_temporary_files(tmp_path):
    client = MemoryS3()
    store = S3PrivateObjectStore(client=client, bucket="synthetic-private")
    source = tmp_path / "synthetic.pdf"
    source.write_bytes(pdf_bytes())
    checksum = hashlib.sha256(source.read_bytes()).hexdigest()
    store.put_file("synthetic/source.pdf", source, checksum, "application/pdf")
    with store.materialize("synthetic/source.pdf", checksum) as staged:
        assert staged.read_bytes() == source.read_bytes()
    assert not staged.exists()
    with pytest.raises(Exception, match="integrity"):
        with store.materialize("synthetic/source.pdf", "0" * 64):
            pass
    store.delete_file("synthetic/source.pdf")
    assert client.objects == {}


@pytest.mark.parametrize(
    "key", ["../source.pdf", "/absolute.pdf", "a/../../source.pdf", "a\\source.pdf", "s3://bucket/key"]
)
def test_remote_keys_cannot_escape_private_namespace(key, tmp_path):
    store = S3PrivateObjectStore(client=MemoryS3(), bucket="synthetic")
    with pytest.raises(Exception, match="Illegal storage"):
        store.put_file(key, tmp_path / "source", "0" * 64, "application/pdf")


def test_mixed_storage_preserves_old_local_downloads(client, patient_token, db_session, monkeypatch):
    local = upload(client, patient_token).json()["document"]
    fake = MemoryS3()
    monkeypatch.setattr(storage_service, "s3", S3PrivateObjectStore(client=fake, bucket="synthetic"))
    monkeypatch.setattr(settings, "STORAGE_BACKEND", "s3")
    remote_response = upload(client, patient_token)
    assert remote_response.status_code == 201, remote_response.text
    remote = remote_response.json()["document"]
    assert db_session.get(MedicalDocument, local["id"]).storage_backend == "local"
    assert db_session.get(MedicalDocument, remote["id"]).storage_backend == "s3"
    for doc in (local, remote):
        assert (
            client.get(f"/api/v1/documents/{doc['id']}/download", headers=headers(patient_token)).content
            == pdf_bytes()
        )
    assert len(fake.objects) == 1


def test_production_tls_applies_to_old_remote_documents_even_when_new_uploads_are_local():
    with pytest.raises(ValueError, match="HTTPS"):
        Settings(
            SECRET_KEY="synthetic-config-key-not-for-real-deployment",
            ENVIRONMENT="production",
            STORAGE_BACKEND="local",
            S3_ENDPOINT_URL="http://synthetic-private-storage",
            S3_ACCESS_KEY_ID="synthetic-access",
            S3_SECRET_ACCESS_KEY="synthetic-secret",
        )
