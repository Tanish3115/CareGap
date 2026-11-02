"""Separate patient accounts from historical prescriptions and clinician assessments."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import update
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.api.clinical import authorize_patient, authorized_record
from app.core.errors import PermissionDeniedException
from app.core.time import utc_now
from app.models.document import MedicalDocument
from app.models.document_review import DocumentReviewRevision
from app.models.medication_use import MedicationUse, MedicationUseRevision, MedicationReconciliation
from app.models.prescription import MedicationEntry, PrescriptionRevision
from app.models.user import User
from app.schemas.medication_use import ReportCreate, ReportCorrect, ReportOut, ReconcileInput, ReviewOut
from app.services.authorization import require_document_access
from app.services.audit_service import audit_service

router = APIRouter(prefix="/clinical/medication-use", tags=["Reported medication use and reconciliation"])


def source_snapshot(db, user, patient_id, entry_id, request):
    if entry_id is None:
        return None
    entry = db.get(MedicationEntry, str(entry_id))
    if not entry or entry.patient_id != patient_id:
        raise HTTPException(422, "Source must be a historical prescription entry belonging to this patient")
    doc = db.get(MedicalDocument, entry.document_id)
    require_document_access(db, user, doc, request)
    prescription = db.get(PrescriptionRevision, entry.prescription_revision_id)
    review = db.get(DocumentReviewRevision, prescription.source_review_id)
    latest_confirmed = (
        db.query(PrescriptionRevision.version)
        .filter_by(document_id=doc.id, state="clinician_confirmed")
        .order_by(PrescriptionRevision.version.desc())
        .first()
    )
    return dict(
        entry_id=entry.id,
        document_id=doc.id,
        title=doc.title,
        file_name=doc.file_name,
        prescription_version=prescription.version,
        source_review_version=review.version,
        current_source_review_version=doc.review_version,
        current_prescription_version=doc.prescription_version,
        source_stale=review.version != doc.review_version,
        superseded=latest_confirmed[0] != prescription.version,
        draft_pending=doc.prescription_version > latest_confirmed[0],
        **{
            name: getattr(entry, name)
            for name in ("name", "strength", "dose", "route", "frequency", "duration", "instructions")
        },
    )


def review_out(db, review):
    return dict(
        id=review.id,
        version=review.version,
        report_version=db.get(MedicationUseRevision, review.report_revision_id).version,
        assessment=review.assessment,
        note=review.note,
        source_snapshot=review.source_snapshot,
        recorded_by_name=db.get(User, review.recorded_by).full_name,
        created_at=review.created_at,
    )


def report_out(db, root, revision, user, request):
    source = source_snapshot(db, user, root.patient_id, revision.source_entry_id, request)
    review = (
        db.query(MedicationReconciliation)
        .filter_by(medication_use_id=root.id, version=root.review_version)
        .first()
    )
    return dict(
        id=root.id,
        patient_id=root.patient_id,
        version=revision.version,
        review_version=root.review_version,
        **{
            name: getattr(revision, name)
            for name in (
                "name",
                "dose",
                "frequency",
                "use_status",
                "reported_on",
                "notes",
                "source_entry_id",
                "reason",
            )
        },
        source=source,
        recorded_by_name=db.get(User, revision.recorded_by).full_name,
        created_at=revision.created_at,
        latest_review=review_out(db, review) if review else None,
        review_stale=bool(
            review and (review.report_revision_id != revision.id or review.source_snapshot != source)
        ),
    )


def patient_only(user):
    if user.role != "patient":
        raise PermissionDeniedException(
            "Only the patient can create or correct their reported medication use"
        )


def log(db, user, root, action, commit=True):
    audit_service.log_event(
        db,
        action,
        "medication_use",
        actor_id=user.id,
        patient_id=root.patient_id,
        resource_id=root.id,
        commit=commit,
    )


@router.post("", response_model=ReportOut, status_code=201)
def create_report(
    payload: ReportCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient_only(user)
    patient_id = str(payload.patient_id)
    authorize_patient(db, user, patient_id, request, write=True, resource="medications")
    source_snapshot(db, user, patient_id, payload.source_entry_id, request)
    root = MedicationUse(patient_id=patient_id)
    db.add(root)
    db.flush()
    values = payload.model_dump(exclude={"patient_id"}, mode="python")
    values["source_entry_id"] = str(payload.source_entry_id) if payload.source_entry_id else None
    revision = MedicationUseRevision(medication_use_id=root.id, version=1, recorded_by=user.id, **values)
    db.add(revision)
    log(db, user, root, "REPORT_MEDICATION_USE", commit=False)
    db.commit()
    return report_out(db, root, revision, user, request)


@router.get("", response_model=list[ReportOut])
def list_reports(
    patient_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    target = str(patient_id)
    authorize_patient(db, user, target, request, resource="medications")
    rows = (
        db.query(MedicationUse, MedicationUseRevision)
        .join(
            MedicationUseRevision,
            (MedicationUseRevision.medication_use_id == MedicationUse.id)
            & (MedicationUseRevision.version == MedicationUse.version),
        )
        .filter(MedicationUse.patient_id == target)
        .order_by(MedicationUse.updated_at.desc(), MedicationUse.id)
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [report_out(db, root, revision, user, request) for root, revision in rows]
    audit_service.log_event(db, "VIEW_MEDICATION_USE", "medication_use", actor_id=user.id, patient_id=target)
    return result


@router.put("/{record_id}", response_model=ReportOut)
def correct_report(
    record_id: UUID,
    payload: ReportCorrect,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    patient_only(user)
    root = authorized_record(db, MedicationUse, record_id, user, request, write=True)
    source_snapshot(db, user, root.patient_id, payload.source_entry_id, request)
    changed = db.execute(
        update(MedicationUse)
        .where(MedicationUse.id == root.id, MedicationUse.version == payload.expected_version)
        .values(version=payload.expected_version + 1, updated_at=utc_now())
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Medication report changed. Reload before correcting.")
    values = payload.model_dump(exclude={"expected_version"}, mode="python")
    values["source_entry_id"] = str(payload.source_entry_id) if payload.source_entry_id else None
    revision = MedicationUseRevision(
        medication_use_id=root.id, version=payload.expected_version + 1, recorded_by=user.id, **values
    )
    db.add(revision)
    log(db, user, root, "CORRECT_MEDICATION_USE", commit=False)
    db.commit()
    return report_out(db, root, revision, user, request)


@router.get("/{record_id}/history", response_model=list[ReportOut])
def report_history(
    record_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    root = authorized_record(db, MedicationUse, record_id, user, request)
    rows = (
        db.query(MedicationUseRevision)
        .filter_by(medication_use_id=root.id)
        .order_by(MedicationUseRevision.version.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [report_out(db, root, revision, user, request) for revision in rows]
    log(db, user, root, "VIEW_MEDICATION_USE_HISTORY")
    return result


@router.post("/{record_id}/reconciliation", response_model=ReviewOut, status_code=201)
def reconcile(
    record_id: UUID,
    payload: ReconcileInput,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    root = authorized_record(db, MedicationUse, record_id, user, request, write=True)
    if user.role != "doctor":
        raise PermissionDeniedException(
            "Only a verified clinician with clinical write consent can reconcile a patient report"
        )
    changed = db.execute(
        update(MedicationUse)
        .where(
            MedicationUse.id == root.id,
            MedicationUse.version == payload.expected_report_version,
            MedicationUse.review_version == payload.expected_review_version,
        )
        .values(review_version=payload.expected_review_version + 1)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        db.rollback()
        raise HTTPException(409, "Report or reconciliation changed. Reload before reviewing.")
    revision = (
        db.query(MedicationUseRevision)
        .filter_by(medication_use_id=root.id, version=payload.expected_report_version)
        .one()
    )
    source = source_snapshot(db, user, root.patient_id, revision.source_entry_id, request)
    if source:
        if (
            payload.expected_source_review_version != source["current_source_review_version"]
            or payload.expected_prescription_version != source["current_prescription_version"]
        ):
            db.rollback()
            raise HTTPException(409, "Prescription source changed. Reload the comparison before reviewing.")
        locked = db.execute(
            update(MedicalDocument)
            .where(
                MedicalDocument.id == source["document_id"],
                MedicalDocument.review_version == source["current_source_review_version"],
                MedicalDocument.prescription_version == source["current_prescription_version"],
            )
            .values(prescription_version=MedicalDocument.prescription_version)
            .execution_options(synchronize_session=False)
        )
        if locked.rowcount != 1:
            db.rollback()
            raise HTTPException(409, "Prescription source changed. Reload before reviewing.")
    elif (
        payload.expected_source_review_version is not None
        or payload.expected_prescription_version is not None
    ):
        db.rollback()
        raise HTTPException(422, "This patient report has no linked prescription source")
    review = MedicationReconciliation(
        medication_use_id=root.id,
        report_revision_id=revision.id,
        version=payload.expected_review_version + 1,
        assessment=payload.assessment,
        note=payload.note,
        source_snapshot=source,
        recorded_by=user.id,
    )
    db.add(review)
    log(db, user, root, "RECONCILE_MEDICATION_USE", commit=False)
    db.commit()
    return review_out(db, review)


@router.get("/{record_id}/reconciliation/history", response_model=list[ReviewOut])
def review_history(
    record_id: UUID,
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    root = authorized_record(db, MedicationUse, record_id, user, request)
    rows = (
        db.query(MedicationReconciliation)
        .filter_by(medication_use_id=root.id)
        .order_by(MedicationReconciliation.version.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    result = [review_out(db, row) for row in rows]
    log(db, user, root, "VIEW_RECONCILIATION_HISTORY")
    return result
