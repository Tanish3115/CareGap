"""Shared clinical identity/provenance; strictly typed versioned resource payloads."""

import uuid
from datetime import date, datetime
from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.time import utc_now
from app.database import Base

KINDS = (
    "diagnosis",
    "allergy",
    "lab",
    "appointment",
    "referral",
    "test",
    "medication_order",
    "dispensing",
    "confirmed_use",
    "intervention",
)


class HealthRecord(Base):
    __tablename__ = "health_records"
    __table_args__ = (CheckConstraint("version >= 1"), CheckConstraint(f"kind IN {KINDS}"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class HealthRevision(Base):
    __tablename__ = "health_revisions"
    __table_args__ = (
        UniqueConstraint("record_id", "version"),
        CheckConstraint("version >= 1"),
        CheckConstraint("provenance IN ('patient_reported','clinician_recorded')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    record_id: Mapped[str] = mapped_column(ForeignKey("health_records.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    occurred_on: Mapped[date] = mapped_column(Date)
    data: Mapped[dict] = mapped_column(JSON)
    recorded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provenance: Mapped[str] = mapped_column(String(30))
    reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    sources: Mapped[list["HealthSource"]] = relationship(lazy="selectin")


class HealthSource(Base):
    __tablename__ = "health_sources"
    revision_id: Mapped[str] = mapped_column(ForeignKey("health_revisions.id"), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("medical_documents.id"), primary_key=True)
    document = relationship("MedicalDocument", lazy="joined")
