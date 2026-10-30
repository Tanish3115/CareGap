import hashlib
import warnings
from pathlib import Path
from uuid import UUID, uuid4
from fastapi import UploadFile
from PIL import Image
from pypdf import PdfReader
from starlette.concurrency import run_in_threadpool
from app.config import settings
from app.core.errors import InvalidFileException

Image.MAX_IMAGE_PIXELS = 25_000_000


class StorageService:
    MIME = {".pdf": "application/pdf", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}

    def __init__(self, base_storage_dir=None):
        self.base_dir = Path(base_storage_dir or settings.STORAGE_DIR).resolve()

    def resolve(self, relative_path):
        target = (self.base_dir / relative_path).resolve()
        if not target.is_relative_to(self.base_dir) or target == self.base_dir:
            raise InvalidFileException("Illegal storage path")
        return target

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
            raise InvalidFileException("File content is invalid, unsupported, encrypted or too complex") from exc

    async def save_patient_document(self, patient_id: str, file: UploadFile):
        try:
            patient_id = str(UUID(patient_id))
        except (ValueError, TypeError) as exc:
            raise InvalidFileException("Invalid patient identifier") from exc
        filename = (file.filename or "").replace("\\", "/").split("/")[-1]
        ext = Path(filename).suffix.lower()
        if not filename or len(filename) > 255 or ext not in self.MIME:
            raise InvalidFileException("File extension is not permitted")
        if file.content_type not in {self.MIME[ext], "image/jpg" if ext in {".jpg", ".jpeg"} else self.MIME[ext]}:
            raise InvalidFileException("File MIME type does not match extension")
        relative = f"{patient_id}/{uuid4()}{ext}"
        target = self.resolve(relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        total = 0
        digest = hashlib.sha256()
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
        except Exception:
            target.unlink(missing_ok=True)
            raise
        finally:
            await file.close()
        return relative, filename, total, digest.hexdigest()

    def delete_file(self, relative):
        self.resolve(relative).unlink(missing_ok=True)

    def get_secure_file_path(self, relative_path, expected_sha256=None):
        target = self.resolve(relative_path)
        if not target.is_file():
            raise InvalidFileException("Document file is unavailable")
        if expected_sha256:
            with target.open("rb") as source:
                checksum = hashlib.file_digest(source, "sha256").hexdigest()
            if checksum != expected_sha256:
                raise InvalidFileException("Document integrity check failed")
        return target


storage_service = StorageService()
