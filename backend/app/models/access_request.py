from app.core.time import utc_now
import uuid
from datetime import datetime
from sqlalchemy import (
    String,
    DateTime,
    ForeignKey,
    Integer,
    CheckConstraint,
    Boolean,
    Index,
    JSON,
    text,
    false,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.core.clinical_resources import CLINICAL_RESOURCES


class AccessRequest(Base):
    __tablename__ = "access_requests"
    __table_args__ = (
        CheckConstraint("scope IN ('all', 'prescriptions_only', 'labs_only')"),
        CheckConstraint("status IN ('pending', 'approved', 'denied')"),
        CheckConstraint("duration_hours >= 1 AND duration_hours <= 720"),
        Index(
            "uq_pending_access_request",
            "patient_id",
            "doctor_id",
            unique=True,
            sqlite_where=text("status = 'pending'"),
            postgresql_where=text("status = 'pending'"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"), index=True)
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(50))
    purpose: Mapped[str] = mapped_column(String(255))
    duration_hours: Mapped[int] = mapped_column(Integer)
    allow_upload: Mapped[bool] = mapped_column(Boolean, default=False)
    include_clinical_records: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    allow_clinical_write: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    clinical_resources: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=lambda: sorted(CLINICAL_RESOURCES)
    )
    status: Mapped[str] = mapped_column(String(20), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    grant_id: Mapped[str | None] = mapped_column(ForeignKey("consent_grants.id"), nullable=True)
