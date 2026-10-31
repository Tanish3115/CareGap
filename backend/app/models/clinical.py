"""Stable clinical identities with append-only, attributed revision snapshots."""
import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.database import Base


def new_id():
    return str(uuid.uuid4())


class Encounter(Base):
    __tablename__ = "encounters"
    __table_args__ = (CheckConstraint("version >= 1"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class EncounterRevision(Base):
    __tablename__ = "encounter_revisions"
    __table_args__ = (
        UniqueConstraint("encounter_id", "version"), CheckConstraint("version >= 1"),
        CheckConstraint("provenance IN ('patient_reported', 'clinician_recorded')"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    occurred_on: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(255))
    notes: Mapped[str] = mapped_column(Text)
    recorded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provenance: Mapped[str] = mapped_column(String(30))
    correction_reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    sources: Mapped[list["EncounterSource"]] = relationship(lazy="selectin")


class EncounterSource(Base):
    __tablename__ = "encounter_sources"

    revision_id: Mapped[str] = mapped_column(ForeignKey("encounter_revisions.id"), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("medical_documents.id"), primary_key=True)
    document = relationship("MedicalDocument", lazy="joined")


class FollowUpTask(Base):
    __tablename__ = "follow_up_tasks"
    __table_args__ = (CheckConstraint("version >= 1"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    encounter_id: Mapped[str] = mapped_column(ForeignKey("encounters.id"), index=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class FollowUpRevision(Base):
    __tablename__ = "follow_up_revisions"
    __table_args__ = (
        UniqueConstraint("task_id", "version"), CheckConstraint("version >= 1"),
        CheckConstraint("status IN ('pending', 'completed', 'cancelled')"),
        CheckConstraint("provenance IN ('patient_reported', 'clinician_recorded')"),
        CheckConstraint("status = 'pending' OR outcome IS NOT NULL"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    task_id: Mapped[str] = mapped_column(ForeignKey("follow_up_tasks.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    due_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))
    outcome: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    provenance: Mapped[str] = mapped_column(String(30))
    correction_reason: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
