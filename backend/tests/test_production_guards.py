import hashlib
import pytest
from app.config import Settings, settings
from app.services.object_storage import S3PrivateObjectStore

KEY = "synthetic-settings-key-only-not-a-production-secret"


def test_production_requires_shared_limit_store_verified_encryption_and_postgres():
    with pytest.raises(ValueError, match="shared Redis"):
        Settings(SECRET_KEY=KEY, ENVIRONMENT="production", S3_ENDPOINT_URL=None)
    with pytest.raises(ValueError, match="encrypted volumes"):
        Settings(
            SECRET_KEY=KEY,
            ENVIRONMENT="production",
            RATE_LIMIT_STORAGE_URI="rediss://synthetic.invalid",
            S3_ENDPOINT_URL=None,
        )
    configured = Settings(
        SECRET_KEY=KEY,
        ENVIRONMENT="production",
        RATE_LIMIT_STORAGE_URI="rediss://synthetic.invalid",
        LOCAL_VOLUME_ENCRYPTION_VERIFIED=True,
        DATABASE_URL="postgresql+psycopg://synthetic.invalid/example",
        S3_ENDPOINT_URL=None,
    )
    assert configured.LOCAL_VOLUME_ENCRYPTION_VERIFIED
    with pytest.raises(ValueError, match="KMS"):
        Settings(SECRET_KEY=KEY, S3_SERVER_SIDE_ENCRYPTION="aws:kms", S3_KMS_KEY_ID="")


def test_encrypted_object_upload_sends_explicit_server_side_encryption_parameters(tmp_path, monkeypatch):
    captured = {}

    class Provider:
        def put_object(self, **kwargs):
            captured.update({key: value for key, value in kwargs.items() if key != "Body"})

    source = tmp_path / "synthetic.pdf"
    source.write_bytes(b"Synthetic encryption fixture")
    monkeypatch.setattr(settings, "S3_SERVER_SIDE_ENCRYPTION", "AES256")
    S3PrivateObjectStore(client=Provider(), bucket="synthetic-private").put_file(
        "synthetic/source.pdf", source, hashlib.sha256(source.read_bytes()).hexdigest(), "application/pdf"
    )
    assert captured["ServerSideEncryption"] == "AES256" and "ACL" not in captured
