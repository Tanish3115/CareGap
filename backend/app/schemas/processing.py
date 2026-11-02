from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class OCRWord(BaseModel):
    text: str = Field(max_length=500)
    confidence: float = Field(ge=0, le=100)
    left: int = Field(ge=0)
    top: int = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)


class SourcePage(BaseModel):
    page_number: int = Field(ge=1, le=200)
    method: Literal["pdf_text", "tesseract", "unavailable", "not_processed"]
    text: str = Field(max_length=100000)
    confidence: float | None = Field(default=None, ge=0, le=100)
    words: list[OCRWord] = Field(default_factory=list, max_length=2000)
    warning: (
        Literal[
            "ocr_disabled",
            "ocr_unavailable",
            "ocr_failed",
            "renderer_unavailable",
            "renderer_failed",
            "word_limit",
            "page_limit",
            "no_text_detected",
            "text_limit",
        ]
        | None
    ) = None


class SourceTextResult(BaseModel):
    kind: Literal["pdf_text", "image"]
    text: str = Field(max_length=100000)
    source_sha256: str = Field(pattern="^[a-f0-9]{64}$")
    page_count: int = Field(ge=1, le=200)
    needs_ocr: bool
    truncated: bool
    verification_status: Literal["unverified"] = "unverified"
    processor_version: Literal["source-text-v1", "source-ocr-v2"] = "source-text-v1"
    pages: list[SourcePage] = Field(default_factory=list, max_length=200)


class ProcessingJobOut(BaseModel):
    id: str | None
    document_id: str
    status: Literal["not_queued", "queued", "processing", "succeeded", "failed"]
    attempts: int
    max_attempts: int = 3
    error_code: str | None
    result: SourceTextResult | None
    started_at: datetime | None
    finished_at: datetime | None
    can_retry: bool
    can_view_review: bool = False
    can_review: bool = False
    can_view_prescription: bool = False
    can_edit_prescription: bool = False
    can_reprocess: bool = False
