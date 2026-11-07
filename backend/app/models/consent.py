from app.core.time import utc_now
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON, false
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.core.clinical_resources import CLINICAL_RESOURCES


class ConsentScope(str, Enum):
    ALL = "all"
    PRESCRIPTIONS_ONLY = "prescriptions_only"
    LABS_ONLY = "labs_only"


class ConsentGrant(Base):
    __tablename__ = "consent_grants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("patients.id", ondelete="CASCADE"), index=True, nullable=False
    )
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id", ondelete="CASCADE"), index=True, nullable=False
    )
    organization_id: Mapped[str | None] = mapped_column(ForeignKey("organizations.id"), nullable=True)
    scope: Mapped[str] = mapped_column(String(50), default=ConsentScope.ALL.value, nullable=False)
    purpose: Mapped[str] = mapped_column(String(255), nullable=False)
    allow_upload: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    include_clinical_records: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    allow_clinical_write: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    document_ids: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    clinical_resources: Mapped[list[str] | None] = mapped_column(
        JSON, nullable=True, default=lambda: sorted(CLINICAL_RESOURCES)
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
    valid_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="consent_grants")
    doctor = relationship("Doctor", back_populates="consent_grants")
