import hashlib
import os
import shutil
import uuid
from pathlib import Path
from typing import BinaryIO
from fastapi import UploadFile
from app.config import settings
from app.core.errors import InvalidFileException


class StorageService:
    def __init__(self, base_storage_dir: str = settings.STORAGE_DIR):
        self.base_dir = Path(base_storage_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def validate_file(self, file: UploadFile) -> None:
        """Validate filename extension and MIME type against allowed list."""
        if not file.filename:
            raise InvalidFileException("Filename cannot be empty")

        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise InvalidFileException(
                f"File extension '{ext}' is not permitted. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
            )

        if file.content_type and file.content_type.lower() not in settings.ALLOWED_MIME_TYPES:
            raise InvalidFileException(
                f"MIME type '{file.content_type}' is not permitted. Allowed: {', '.join(settings.ALLOWED_MIME_TYPES)}"
            )

    async def save_patient_document(
        self, patient_id: str, file: UploadFile
    ) -> tuple[str, str, int, str]:
        """
        Securely save an uploaded medical document for a patient.
        Returns: (stored_relative_path, original_filename, file_size, sha256_hash)
        """
        self.validate_file(file)

        # Enforce patient directory isolation
        patient_dir = (self.base_dir / patient_id).resolve()
        # Prevent directory traversal
        if not str(patient_dir).startswith(str(self.base_dir)):
            raise InvalidFileException("Illegal storage path")
        patient_dir.mkdir(parents=True, exist_ok=True)

        ext = Path(file.filename).suffix.lower()
        unique_file_id = f"{uuid.uuid4()}{ext}"
        target_path = patient_dir / unique_file_id

        hasher = hashlib.sha256()
        total_size = 0

        try:
            with open(target_path, "wb") as buffer:
                while chunk := await file.read(1024 * 64):  # 64KB chunks
                    total_size += len(chunk)
                    if total_size > settings.MAX_FILE_SIZE_BYTES:
                        raise InvalidFileException(
                            f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)}MB"
                        )
                    hasher.update(chunk)
                    buffer.write(chunk)
        except Exception:
            if target_path.exists():
                target_path.unlink()
            raise

        sha256_hash = hasher.hexdigest()
        relative_path = f"{patient_id}/{unique_file_id}"
        return relative_path, file.filename, total_size, sha256_hash

    def get_secure_file_path(self, relative_path: str) -> Path:
        """Resolve and verify that the requested file resides securely within the storage directory."""
        target = (self.base_dir / relative_path).resolve()
        if not str(target).startswith(str(self.base_dir)) or not target.is_file():
            raise InvalidFileException("Requested document file does not exist or access path is invalid")
        return target


storage_service = StorageService()

