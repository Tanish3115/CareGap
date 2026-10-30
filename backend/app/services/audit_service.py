from typing import Optional
from sqlalchemy.orm import Session
from app.models.audit import AuditLog, AuditAction


class AuditService:
    @staticmethod
    def log_event(
        db: Session,
        action: AuditAction | str,
        resource_type: str,
        actor_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        details: Optional[str] = None,
        commit: bool = True,
    ) -> AuditLog:
        """Create an immutable audit log record for security, access compliance and traceability."""
        act_val = action.value if isinstance(action, AuditAction) else str(action)
        audit_entry = AuditLog(
            actor_id=actor_id,
            patient_id=patient_id,
            action=act_val,
            resource_type=resource_type,
            resource_id=resource_id,
            ip_address=ip_address,
            details=details,
        )
        db.add(audit_entry)
        if commit:
            db.commit()
            db.refresh(audit_entry)
        else:
            db.flush()
        return audit_entry


audit_service = AuditService()

