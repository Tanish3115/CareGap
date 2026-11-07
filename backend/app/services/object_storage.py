"""Private storage boundary; local materialization keeps consumers provider-independent."""

import hashlib
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import ContextManager, Protocol

from botocore.exceptions import ClientError

from app.config import settings
from app.core.errors import InvalidFileException


class PrivateObjectStore(Protocol):
    def materialize(self, key: str, checksum: str) -> ContextManager[Path]: ...
    def delete_file(self, key: str) -> None: ...
    def put_file(self, key: str, path: Path, checksum: str, mime_type: str) -> None: ...


def validate_key(key):
    if (
        not key
        or "\\" in key
        or ":" in key
        or PurePosixPath(key).is_absolute()
        or any(part in {"", ".", ".."} for part in key.split("/"))
    ):
        raise InvalidFileException("Illegal storage key")
    return key


class LocalPrivateObjectStore:
    def __init__(self, base_storage_dir=None):
        self.base_dir = Path(base_storage_dir or settings.STORAGE_DIR).resolve()

    def resolve(self, key):
        validate_key(key)
        target = (self.base_dir / key).resolve()
        if Path(key).is_absolute() or not target.is_relative_to(self.base_dir) or target == self.base_dir:
            raise InvalidFileException("Illegal storage path")
        return target

    def delete_file(self, key):
        self.resolve(key).unlink(missing_ok=True)

    def get_secure_file_path(self, key, expected_sha256=None):
        target = self.resolve(key)
        if not target.is_file():
            raise InvalidFileException("Document file is unavailable")
        if expected_sha256:
            with target.open("rb") as source:
                checksum = hashlib.file_digest(source, "sha256").hexdigest()
            if checksum != expected_sha256:
                raise InvalidFileException("Document integrity check failed")
        return target

    @contextmanager
    def materialize(self, key, checksum):
        yield self.get_secure_file_path(key, checksum)


class S3PrivateObjectStore:
    """Private SDK-only access. No public ACLs, unsigned reads or public URLs."""

    def __init__(self, client=None, bucket=None):
        self._client = client
        self.bucket = bucket or settings.S3_BUCKET

    @property
    def client(self):
        if self._client is None:
            import boto3
            from botocore.config import Config

            if (
                not settings.S3_ACCESS_KEY_ID.get_secret_value()
                or not settings.S3_SECRET_ACCESS_KEY.get_secret_value()
            ):
                raise InvalidFileException("Private object storage is not configured")
            self._client = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                region_name=settings.S3_REGION,
                aws_access_key_id=settings.S3_ACCESS_KEY_ID.get_secret_value(),
                aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY.get_secret_value(),
                config=Config(
                    **(
                        {
                            "request_checksum_calculation": "when_required",
                            "response_checksum_validation": "when_required",
                        }
                        if settings.S3_PROVIDER == "supabase"
                        else {}
                    ),
                    signature_version="s3v4",
                    s3={"addressing_style": "path"},
                    connect_timeout=5,
                    read_timeout=20,
                    retries={"max_attempts": 2},
                ),
            )
        return self._client

    def put_file(self, key, path, checksum, mime_type):
        self._put_file(key, path, checksum, mime_type)

    def put_file_if_absent(self, key, path, checksum, mime_type):
        """Never overwrite a destination; the caller must verify reused bytes."""
        self._put_file(key, path, checksum, mime_type, only_if_absent=True)

    def _put_file(self, key, path, checksum, mime_type, only_if_absent=False):
        validate_key(key)
        encryption = {}
        if settings.S3_SERVER_SIDE_ENCRYPTION:
            encryption["ServerSideEncryption"] = settings.S3_SERVER_SIDE_ENCRYPTION
            if settings.S3_SERVER_SIDE_ENCRYPTION == "aws:kms":
                encryption["SSEKMSKeyId"] = settings.S3_KMS_KEY_ID.get_secret_value()
        try:
            with Path(path).open("rb") as source:
                self.client.put_object(
                    Bucket=self.bucket,
                    Key=key,
                    Body=source,
                    ContentType=mime_type,
                    Metadata={"sha256": checksum},
                    **({"IfNoneMatch": "*"} if only_if_absent else {}),
                    **encryption,
                )
        except ClientError as exc:
            if only_if_absent and str(exc.response.get("Error", {}).get("Code")) in {
                "PreconditionFailed",
                "412",
            }:
                return
            raise InvalidFileException("Private object upload failed") from exc
        except Exception as exc:
            raise InvalidFileException("Private object upload failed") from exc

    def delete_file(self, key):
        validate_key(key)
        try:
            self.client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:
            raise InvalidFileException("Private object cleanup failed") from exc

    @contextmanager
    def materialize(self, key, checksum):
        validate_key(key)
        with tempfile.TemporaryDirectory(prefix="caregap-object-") as folder:
            target = Path(folder) / ("source" + PurePosixPath(key).suffix)
            body = None
            try:
                response = self.client.get_object(Bucket=self.bucket, Key=key)
                body = response["Body"]
                if int(response.get("ContentLength", 0)) > settings.MAX_FILE_SIZE_BYTES:
                    raise ValueError("Excessive source size")
                digest, size = hashlib.sha256(), 0
                with target.open("xb") as output:
                    while chunk := body.read(65536):
                        size += len(chunk)
                        if size > settings.MAX_FILE_SIZE_BYTES:
                            raise ValueError("Excessive source size")
                        output.write(chunk)
                        digest.update(chunk)
                if not size or digest.hexdigest() != checksum:
                    raise ValueError("Integrity mismatch")
            except Exception as exc:
                raise InvalidFileException(
                    "Private object is unavailable or failed integrity checks"
                ) from exc
            finally:
                if body is not None:
                    body.close()
            yield target
