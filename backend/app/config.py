from pathlib import Path
from typing import Literal
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CareGap 360"
    VERSION: str = "0.1.0"
    API_V1_PREFIX: str = "/api/v1"
    
    # Security
    SECRET_KEY: str = Field(min_length=32)
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    COOKIE_SECURE: bool = False
    ALGORITHM: Literal["HS256"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    # Database
    DATABASE_URL: str = "sqlite:///./caregap360.db"
    
    # File Storage
    STORAGE_DIR: str = str(Path(__file__).resolve().parent.parent / "storage" / "documents")
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

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parent.parent / ".env",
        case_sensitive=True,
        extra="allow",
    )


settings = Settings()

