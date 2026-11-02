"""Transactional enqueue and compare-and-set leases; safe for multiple workers."""

from datetime import timedelta
from uuid import uuid4
from sqlalchemy import and_, or_, update
from app.core.time import utc_now
from app.models.processing import DocumentProcessingJob
from app.models.document import MedicalDocument
from app.services.audit_service import audit_service

MAX_ATTEMPTS = 3
LEASE_SECONDS = 300


def claim_job(db):
    now = utc_now()
    expired = and_(DocumentProcessingJob.status == "processing", DocumentProcessingJob.lease_until <= now)
    db.execute(
        update(DocumentProcessingJob)
        .where(expired, DocumentProcessingJob.attempts >= MAX_ATTEMPTS)
        .values(
            status="failed",
            error_code="lease_exhausted",
            lease_token=None,
            lease_until=None,
            result=None,
            finished_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    eligible = or_(DocumentProcessingJob.status == "queued", expired)
    candidates = (
        db.query(DocumentProcessingJob.id)
        .filter(eligible, DocumentProcessingJob.attempts < MAX_ATTEMPTS)
        .order_by(DocumentProcessingJob.created_at, DocumentProcessingJob.id)
        .limit(20)
        .all()
    )
    for (job_id,) in candidates:
        token = str(uuid4())
        result = db.execute(
            update(DocumentProcessingJob)
            .where(
                DocumentProcessingJob.id == job_id, eligible, DocumentProcessingJob.attempts < MAX_ATTEMPTS
            )
            .values(
                status="processing",
                attempts=DocumentProcessingJob.attempts + 1,
                lease_token=token,
                lease_until=now + timedelta(seconds=LEASE_SECONDS),
                started_at=now,
                finished_at=None,
                error_code=None,
                result=None,
            )
            .execution_options(synchronize_session=False)
        )
        if result.rowcount == 1:
            db.commit()
            return job_id, token
    db.commit()
    return None


def finish_job(db, job_id, token, result=None, error_code=None):
    now = utc_now()
    changed = db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.id == job_id,
            DocumentProcessingJob.status == "processing",
            DocumentProcessingJob.lease_token == token,
            DocumentProcessingJob.lease_until > now,
        )
        .values(
            status="failed" if error_code else "succeeded",
            result=result,
            error_code=error_code,
            lease_token=None,
            lease_until=None,
            finished_at=now,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount == 1:
        job = db.get(DocumentProcessingJob, job_id, populate_existing=True)
        doc = db.get(MedicalDocument, job.document_id)
        audit_service.log_event(
            db,
            "PROCESS_DOCUMENT",
            "document",
            patient_id=doc.patient_id,
            resource_id=doc.id,
            details=f"status={job.status};attempts={job.attempts}",
            commit=False,
        )
    db.commit()
    return changed.rowcount == 1
