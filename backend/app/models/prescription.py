import uuid
from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.time import utc_now
from app.database import Base


class PrescriptionRevision(Base):
    __tablename__ = "prescription_revisions"
    __table_args__ = (
        UniqueConstraint("document_id", "version"),
        CheckConstraint("version >= 1"),
        CheckConstraint("state IN ('draft','clinician_confirmed')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("medical_documents.id"), index=True)
    source_review_id: Mapped[str] = mapped_column(ForeignKey("document_review_revisions.id"))
    version: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String(30))
    items: Mapped[list] = mapped_column(JSON)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extractor_version: Mapped[str] = mapped_column(String(40))
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    author_role: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MedicationEntry(Base):
    __tablename__ = "medication_entries"
    __table_args__ = (UniqueConstraint("prescription_revision_id", "row_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("medical_documents.id"), index=True)
    prescription_revision_id: Mapped[str] = mapped_column(ForeignKey("prescription_revisions.id"), index=True)
    row_number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(500))
    strength: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dose: Mapped[str | None] = mapped_column(String(500), nullable=True)
    route: Mapped[str | None] = mapped_column(String(500), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[str | None] = mapped_column(String(500), nullable=True)
    instructions: Mapped[str | None] = mapped_column(String(500), nullable=True)
    needs_clarification: Mapped[bool] = mapped_column(Boolean)
    evidence: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
