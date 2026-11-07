import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.core.time import utc_now
from app.database import Base


class FHIRImport(Base):
    __tablename__ = "fhir_imports"
    __table_args__ = (UniqueConstraint("patient_id", "sha256"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(ForeignKey("patients.id"), index=True)
    sha256: Mapped[str] = mapped_column(String(64))
    original: Mapped[dict] = mapped_column(JSON)
    imported_by: Mapped[str] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class FHIRImportLink(Base):
    __tablename__ = "fhir_import_links"
    revision_id: Mapped[str] = mapped_column(ForeignKey("health_revisions.id"), primary_key=True)
    import_id: Mapped[str] = mapped_column(ForeignKey("fhir_imports.id"), index=True)
