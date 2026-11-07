import uuid
from datetime import date, datetime
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.core.time import utc_now
from app.database import Base


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    channels: Mapped[list] = mapped_column(JSON, default=lambda: ["in_app"])
    language: Mapped[str] = mapped_column(String(5), default="en")
    __table_args__ = (
        CheckConstraint("version >= 1"),
        CheckConstraint("language IN ('en','hi','kn','te','ta','ml')", name="ck_notification_language"),
    )


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("patient_id", "record_id", "record_version", "channel", "service_day"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    record_id: Mapped[str] = mapped_column(ForeignKey("health_records.id"))
    record_version: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(20))
    mode: Mapped[str] = mapped_column(String(20), default="local_mock")
    status: Mapped[str] = mapped_column(String(30), default="mock_delivered")
    body: Mapped[str] = mapped_column(String(500))
    service_day: Mapped[date] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)
