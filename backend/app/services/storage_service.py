import hashlib
import warnings
import tempfile
from contextlib import contextmanager, nullcontext
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import UploadFile
from PIL import Image
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool
from app.config import settings
from app.core.errors import InvalidFileException
from app.services.object_storage import LocalPrivateObjectStore, S3PrivateObjectStore

Image.MAX_IMAGE_PIXELS = 25_000_000


class StorageService(LocalPrivateObjectStore):
    MIME = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

    def __init__(self, base_storage_dir=None):
        super().__init__(base_storage_dir)
        self.s3 = S3PrivateObjectStore()

    @contextmanager
    def materialize(self, key, checksum, backend="local"):
        store = self if backend == "local" else self.s3 if backend == "s3" else None
        if store is None:
            raise InvalidFileException("Unknown private storage backend")
        if backend == "local":
            with super().materialize(key, checksum) as path:
                yield path
        else:
            with store.materialize(key, checksum) as path:
                yield path

    def delete_file(self, key, backend=None):
        backend = backend or settings.STORAGE_BACKEND
        if backend == "local":
            return super().delete_file(key)
        if backend == "s3":
            return self.s3.delete_file(key)
        raise InvalidFileException("Unknown private storage backend")

    @classmethod
    def mime_for(cls, filename):
        return cls.MIME[Path(filename).suffix.lower()]

    def validate_content(self, path, ext):
        try:
            if ext == ".pdf":
                with path.open("rb") as source:
                    if source.read(5) != b"%PDF-":
                        raise ValueError("Invalid PDF header")
                    source.seek(0)
                    pdf = PdfReader(source, strict=True)
                    if pdf.is_encrypted or not 1 <= len(pdf.pages) <= 200:
                        raise ValueError("Encrypted, empty or excessive PDF")
            else:
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(path) as image:
                        if image.format != ("PNG" if ext == ".png" else "JPEG"):
                            raise ValueError("Image format mismatch")
                        image.verify()
                    with Image.open(path) as image:
                        image.load()
        except Exception as exc:
            raise InvalidFileException(
                "File content is invalid, unsupported, encrypted or too complex"
            ) from exc

    async def save_patient_document(self, patient_id: str, file: UploadFile):
        try:
            patient_id = str(UUID(patient_id))
        except (ValueError, TypeError) as exc:
            raise InvalidFileException("Invalid patient identifier") from exc
        filename = (file.filename or "").replace("\\", "/").split("/")[-1]
        ext = Path(filename).suffix.lower()
        if not filename or len(filename) > 255 or ext not in self.MIME:
            raise InvalidFileException("File extension is not permitted")
        if file.content_type not in {
            self.MIME[ext],
            "image/jpg" if ext in {".jpg", ".jpeg"} else self.MIME[ext],
        }:
            raise InvalidFileException("File MIME type does not match extension")
        relative = f"{patient_id}/{uuid4()}{ext}"
        total = 0
        digest = hashlib.sha256()
        remote = settings.STORAGE_BACKEND == "s3"
        with tempfile.TemporaryDirectory(prefix="caregap-upload-") if remote else nullcontext(None) as folder:
            target = Path(folder) / ("source" + ext) if remote else self.resolve(relative)
            target.parent.mkdir(parents=True, exist_ok=True)
            attempted_remote = False
            try:
                with target.open("xb") as output:
                    while chunk := await file.read(65536):
                        total += len(chunk)
                        if total > settings.MAX_FILE_SIZE_BYTES:
                            raise InvalidFileException("File exceeds maximum allowed size")
                        output.write(chunk)
                        digest.update(chunk)
                if not total:
                    raise InvalidFileException("File cannot be empty")
                await run_in_threadpool(self.validate_content, target, ext)
                if remote:
                    attempted_remote = True
                    await run_in_threadpool(
                        self.s3.put_file, relative, target, digest.hexdigest(), self.MIME[ext]
                    )
            except BaseException:
                target.unlink(missing_ok=True)
                if attempted_remote:
                    try:
                        self.s3.delete_file(relative)
                    except Exception:
                        pass
                raise
            finally:
                await file.close()
        return relative, filename, total, digest.hexdigest()


storage_service = StorageService()
