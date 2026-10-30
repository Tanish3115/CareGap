from app.core.time import utc_now
from datetime import datetime
from uuid import uuid4
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class DoctorVerification(Base):
    __tablename__ = "doctor_verifications"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    doctor_id: Mapped[str] = mapped_column(ForeignKey("doctors.id"), index=True)
    reviewer_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(String(20))
    evidence_reference: Mapped[str] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
