import uuid
from datetime import datetime
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.time import utc_now
from app.database import Base


class DocumentReviewRevision(Base):
    __tablename__ = "document_review_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "version"),
        CheckConstraint("version >= 1"),
        CheckConstraint("reviewer_kind IN ('patient_reviewed','clinician_reviewed')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(
        ForeignKey("medical_documents.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    processing_job_id: Mapped[str] = mapped_column(ForeignKey("document_processing_jobs.id"))
    processing_attempt: Mapped[int] = mapped_column(Integer)
    processor_version: Mapped[str] = mapped_column(String(40))
    source_sha256: Mapped[str] = mapped_column(String(64))
    source_text: Mapped[str] = mapped_column(Text)
    reviewed_text: Mapped[str] = mapped_column(Text)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reviewer_kind: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
