from datetime import datetime
from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from app.core.time import utc_now


class SummaryProcessingConsent(Base):
    __tablename__ = "summary_processing_consents"
    __table_args__ = (CheckConstraint("version >= 1", name="ck_summary_consent_version"),)
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    provider_reference: Mapped[str] = mapped_column(String(200), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now, nullable=False)
