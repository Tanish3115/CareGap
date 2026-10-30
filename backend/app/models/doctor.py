from app.core.time import utc_now
import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DoctorVerificationStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    license_number: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    specialization: Mapped[str] = mapped_column(String(100), nullable=False)
    hospital_affiliation: Mapped[str] = mapped_column(String(200), nullable=True)
    verification_status: Mapped[str] = mapped_column(String(20), default=DoctorVerificationStatus.PENDING.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="doctor_profile")
    consent_grants = relationship("ConsentGrant", back_populates="doctor", cascade="all, delete-orphan")

