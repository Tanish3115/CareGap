from app.core.time import utc_now
import uuid
from datetime import datetime, date
from sqlalchemy import String, Text, Date, DateTime, ForeignKey, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.core.identifiers import new_patient_code


class Patient(Base):
    __tablename__ = "patients"
    __table_args__ = (CheckConstraint(
        "length(patient_code) = 4 AND substr(patient_code, 1, 1) BETWEEN 'A' AND 'Z' "
        "AND substr(patient_code, 2, 1) BETWEEN '0' AND '9' "
        "AND substr(patient_code, 3, 1) BETWEEN '0' AND '9' "
        "AND substr(patient_code, 4, 1) BETWEEN '0' AND '9'",
        name="ck_patients_patient_code_format"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_code: Mapped[str] = mapped_column(String(4), unique=True, index=True, nullable=False, default=new_patient_code)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    date_of_birth: Mapped[date] = mapped_column(Date, nullable=True)
    gender: Mapped[str] = mapped_column(String(20), nullable=True)
    blood_group: Mapped[str] = mapped_column(String(10), nullable=True)
    emergency_contact: Mapped[str] = mapped_column(String(100), nullable=True)
    address: Mapped[str] = mapped_column(Text, nullable=True)
    abha_id: Mapped[str] = mapped_column(String(50), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)

    # Relationships
    user = relationship("User", back_populates="patient_profile")
    documents = relationship("MedicalDocument", back_populates="patient", cascade="all, delete-orphan")
    consent_grants = relationship("ConsentGrant", back_populates="patient", cascade="all, delete-orphan")

