from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.api.documents import authorized_document
from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.models.processing import DocumentProcessingJob
from app.models.user import User
from app.schemas.document_review import DocumentReviewIn, DocumentReviewOut
from app.schemas.processing import SourceTextResult
from app.services.authorization import require_clinical_access
from app.services.audit_service import audit_service
from app.services.storage_service import storage_service

router = APIRouter(prefix="/documents", tags=["Source transcription review"])


def review_access(db, user, document_id, request, write=False):
    doc = authorized_document(db, user, document_id, request)
    # Human-added text is clinical content; document-only grants do not expand implicitly.
    require_clinical_access(db, user, doc.patient_id, request, write=write, resource="source_reviews")
    return doc


def review_out(db, item):
    return {
        "document_id": item.document_id,
        "version": item.version,
        "processing_job_id": item.processing_job_id,
        "processing_attempt": item.processing_attempt,
        "processor_version": item.processor_version,
        "source_sha256": item.source_sha256,
        "source_text": item.source_text,
        "reviewed_text": item.reviewed_text,
        "reviewer_id": item.reviewer_id,
        "reviewer_name": db.get(User, item.reviewer_id).full_name,
        "reviewer_kind": item.reviewer_kind,
        "reason": item.reason,
        "created_at": item.created_at,
    }


@router.get("/{document_id}/review", response_model=DocumentReviewOut | None)
def get_review(
    document_id: UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    doc = review_access(db, user, document_id, request)
    item = db.query(DocumentReviewRevision).filter_by(document_id=doc.id, version=doc.review_version).first()
    result = review_out(db, item) if item else None
    audit_service.log_event(
        db, "VIEW_SOURCE_REVIEW", "document", actor_id=user.id, patient_id=doc.patient_id, resource_id=doc.id
    )
    return result


@router.post("/{document_id}/review", response_model=DocumentReviewOut, status_code=201)
def save_review(
    document_id: UUID,
    payload: DocumentReviewIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = review_access(db, user, document_id, request, write=True)
    job = db.query(DocumentProcessingJob).filter_by(document_id=doc.id, status="succeeded").first()
    if not job or job.attempts != payload.expected_attempt or not job.result:
        raise HTTPException(409, "Processing result changed or is not complete. Refresh before reviewing.")
    result = SourceTextResult.model_validate(job.result)
    if result.source_sha256 != doc.sha256_hash:
        raise HTTPException(409, "Processing source does not match this document")
    locked = db.execute(
        update(DocumentProcessingJob)
        .where(
            DocumentProcessingJob.id == job.id,
            DocumentProcessingJob.status == "succeeded",
            DocumentProcessingJob.attempts == payload.expected_attempt,
        )
        .values(attempts=DocumentProcessingJob.attempts)
        .execution_options(synchronize_session=False)
    )
    if locked.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Processing changed. Refresh before reviewing.")
    with storage_service.materialize(doc.file_path, doc.sha256_hash, doc.storage_backend):
        pass
    changed = db.execute(
        update(MedicalDocument)
        .where(MedicalDocument.id == doc.id, MedicalDocument.review_version == payload.expected_version)
        .values(review_version=payload.expected_version + 1)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Review changed. Reload the latest review before saving.")
    item = DocumentReviewRevision(
        document_id=doc.id,
        version=payload.expected_version + 1,
        processing_job_id=job.id,
        processing_attempt=job.attempts,
        processor_version=result.processor_version,
        source_sha256=doc.sha256_hash,
        source_text=result.text,
        reviewed_text=payload.reviewed_text,
        reviewer_id=user.id,
        reviewer_kind="patient_reviewed" if user.role == "patient" else "clinician_reviewed",
        reason=payload.reason,
    )
    db.add(item)
    audit_service.log_event(
        db,
        "REVIEW_SOURCE_TEXT",
        "document",
        actor_id=user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
        details=f"version={item.version}",
        commit=False,
    )
    db.commit()
    return review_out(db, item)


@router.get("/{document_id}/review/history", response_model=list[DocumentReviewOut])
def review_history(
    document_id: UUID,
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = review_access(db, user, document_id, request)
    rows = (
        db.query(DocumentReviewRevision)
        .filter_by(document_id=doc.id)
        .order_by(DocumentReviewRevision.version.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [review_out(db, item) for item in rows]
    audit_service.log_event(
        db,
        "VIEW_SOURCE_REVIEW_HISTORY",
        "document",
        actor_id=user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
    )
    return result
