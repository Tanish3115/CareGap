import uuid
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.time import utc_now
from app.database import Base


class MedicationUse(Base):
    __tablename__ = "medication_uses"
    __table_args__ = (CheckConstraint("version >= 1"), CheckConstraint("review_version >= 0"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    review_version: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MedicationUseRevision(Base):
    __tablename__ = "medication_use_revisions"
    __table_args__ = (
        UniqueConstraint("medication_use_id", "version"),
        CheckConstraint("version >= 1"),
        CheckConstraint("use_status IN ('taking','not_taking','unknown')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_use_id: Mapped[str] = mapped_column(ForeignKey("medication_uses.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(500))
    dose: Mapped[str | None] = mapped_column(String(500), nullable=True)
    frequency: Mapped[str | None] = mapped_column(String(500), nullable=True)
    use_status: Mapped[str] = mapped_column(String(20))
    reported_on: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    source_entry_id: Mapped[str | None] = mapped_column(ForeignKey("medication_entries.id"), nullable=True)
    recorded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class MedicationReconciliation(Base):
    __tablename__ = "medication_reconciliations"
    __table_args__ = (
        UniqueConstraint("medication_use_id", "version"),
        CheckConstraint("version >= 1"),
        CheckConstraint("assessment IN ('account_reviewed','discrepancy','needs_clarification')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    medication_use_id: Mapped[str] = mapped_column(ForeignKey("medication_uses.id"), index=True)
    report_revision_id: Mapped[str] = mapped_column(ForeignKey("medication_use_revisions.id"))
    version: Mapped[int] = mapped_column(Integer)
    assessment: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(String(2000))
    source_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recorded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
