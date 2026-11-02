from pathlib import Path
from typing import Literal
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CareGap 360"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(min_length=32)
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEMO_MODE: bool = False
    COOKIE_SECURE: bool = False
    RATE_LIMIT_STORAGE_URI: SecretStr = SecretStr("memory://")
    LOCAL_VOLUME_ENCRYPTION_VERIFIED: bool = False
    ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    SUMMARY_PROVIDER: Literal["extractive", "http"] = "extractive"
    SUMMARY_PROVIDER_URL: str = ""
    SUMMARY_PROVIDER_TOKEN: SecretStr = SecretStr("")
    SUMMARY_PROVIDER_REFERENCE: str = Field(default="local-source-extracts-v1", min_length=3, max_length=200)
    SUMMARY_PROVIDER_APPROVED: bool = False
    TERMINOLOGY_MODE: Literal["disabled", "synthetic", "approved_catalog"] = "disabled"
    TERMINOLOGY_CATALOG_PATH: str = ""
    TERMINOLOGY_CATALOG_SHA256: str = ""
    TERMINOLOGY_CATALOG_APPROVED: bool = False
    TERMINOLOGY_APPROVAL_REFERENCE: str = ""
    KNOWLEDGE_MODE: Literal["disabled", "approved_catalog"] = "disabled"
    KNOWLEDGE_CATALOG_PATH: str = ""
    KNOWLEDGE_CATALOG_SHA256: str = ""
    KNOWLEDGE_CATALOG_APPROVED: bool = False
    KNOWLEDGE_APPROVAL_REFERENCE: str = ""

    # Database
    DATABASE_URL: str = "sqlite:///./caregap360.db"

    # File Storage
    STORAGE_DIR: str = str(Path(__file__).resolve().parent.parent / "storage" / "documents")
    STORAGE_BACKEND: Literal["local", "s3"] = "local"
    S3_ENDPOINT_URL: str | None = None
    S3_REGION: str = "us-east-1"
    S3_BUCKET: str = "caregap-private"
    S3_ACCESS_KEY_ID: SecretStr = SecretStr("")
    S3_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    S3_SERVER_SIDE_ENCRYPTION: Literal["AES256", "aws:kms"] | None = None
    S3_KMS_KEY_ID: SecretStr = SecretStr("")
    OCR_ENABLED: bool = True
    OCR_MAX_PAGES: int = Field(default=5, ge=1, le=10)
    TESSERACT_COMMAND: str = "tesseract"
    PDFTOPPM_COMMAND: str = "pdftoppm"
    MAX_FILE_SIZE_BYTES: int = 25 * 1024 * 1024  # 25 MB
    ALLOWED_EXTENSIONS: list[str] = [".pdf", ".jpg", ".jpeg", ".png"]
    ALLOWED_MIME_TYPES: list[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/jpg",
    ]

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("SECRET_KEY")
    @classmethod
    def reject_example_keys(cls, value: str) -> str:
        if value.startswith("dev-insecure") or value.startswith("CHANGE_ME"):
            raise ValueError("Generate a private random SECRET_KEY before starting the application")
        return value

    @field_validator("S3_SERVER_SIDE_ENCRYPTION", mode="before")
    @classmethod
    def empty_encryption_mode(cls, value):
        return None if value == "" else value

    @model_validator(mode="after")
    def validate_summary_provider(self):
        if self.SUMMARY_PROVIDER == "http" and self.SUMMARY_PROVIDER_APPROVED:
            from urllib.parse import urlsplit

            url = urlsplit(self.SUMMARY_PROVIDER_URL)
            if url.scheme != "https" or not url.hostname or url.username or url.password or url.fragment:
                raise ValueError(
                    "Approved summary processors require an explicit HTTPS URL without embedded credentials"
                )
            if self.SUMMARY_PROVIDER_REFERENCE == "local-source-extracts-v1":
                raise ValueError("Name the approved summary processor and version explicitly")
        return self

    @model_validator(mode="after")
    def validate_storage(self):
        if self.ENVIRONMENT == "production" and self.DEMO_MODE:
            raise ValueError("Disposable demonstration mode cannot enable production")
        if self.STORAGE_BACKEND == "s3":
            if (
                not self.S3_ACCESS_KEY_ID.get_secret_value()
                or not self.S3_SECRET_ACCESS_KEY.get_secret_value()
            ):
                raise ValueError("S3 requires explicitly configured private credentials")
        if (
            self.ENVIRONMENT == "production"
            and self.S3_ENDPOINT_URL
            and self.S3_ACCESS_KEY_ID.get_secret_value()
            and not self.S3_ENDPOINT_URL.startswith("https://")
        ):
            raise ValueError("Production S3 endpoints require HTTPS")
        if self.S3_SERVER_SIDE_ENCRYPTION == "aws:kms" and not self.S3_KMS_KEY_ID.get_secret_value():
            raise ValueError("KMS encryption requires an explicit key identifier")
        if self.ENVIRONMENT == "production":
            if not self.RATE_LIMIT_STORAGE_URI.get_secret_value().startswith("rediss://"):
                raise ValueError("Production requires a TLS-protected shared Redis rate-limit store")
            if self.STORAGE_BACKEND == "local" and not self.LOCAL_VOLUME_ENCRYPTION_VERIFIED:
                raise ValueError("Production local storage requires independently verified encrypted volumes")
            if self.STORAGE_BACKEND == "s3" and self.S3_SERVER_SIDE_ENCRYPTION is None:
                raise ValueError("Production object uploads require server-side encryption configuration")
            if not self.DATABASE_URL.startswith("postgresql"):
                raise ValueError(
                    "Production requires PostgreSQL with deployment-managed transport encryption"
                )
        return self

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        case_sensitive=True,
        extra="allow",
        hide_input_in_errors=True,
    )


settings = Settings()
