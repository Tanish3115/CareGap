from datetime import datetime, date
from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.core.errors import PermissionDeniedException, ResourceNotFoundException
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.doctor import Doctor
from app.models.document import MedicalDocument, DocumentType, DocumentStatus
from app.models.consent import ConsentGrant
from app.models.audit import AuditAction
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.storage_service import storage_service
from app.services.audit_service import audit_service

router = APIRouter(prefix="/documents", tags=["Medical Documents"])


def _verify_document_access(
    user: User,
    doc: MedicalDocument,
    db: Session,
    request: Request,
) -> bool:
    """
    Enforce patient ownership, active doctor consent grant, or admin role.
    Raises PermissionDeniedException if access is not authorized.
    """
    client_ip = request.client.host if request.client else None

    # 1. Admin has supervisory access (audited)
    if user.role == UserRole.ADMIN.value:
        return True

    # 2. Patient who owns the document
    if user.role == UserRole.PATIENT.value:
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if patient and patient.id == doc.patient_id:
            return True

    # 3. Doctor access requires an active, unrevoked consent grant from this patient
    if user.role == UserRole.DOCTOR.value:
        doctor = db.query(Doctor).filter(Doctor.user_id == user.id).first()
        if doctor:
            now = datetime.utcnow()
            active_grant = (
                db.query(ConsentGrant)
                .filter(
                    ConsentGrant.patient_id == doc.patient_id,
                    ConsentGrant.doctor_id == doctor.id,
                    ConsentGrant.is_revoked == False,
                    ConsentGrant.valid_from <= now,
                    ConsentGrant.valid_until >= now,
                )
                .first()
            )
            if active_grant:
                # Scoped checks: if grant is for labs only and doc is prescription, deny
                if active_grant.scope == "labs_only" and doc.document_type != DocumentType.LAB_REPORT.value:
                    pass
                elif active_grant.scope == "prescriptions_only" and doc.document_type != DocumentType.PRESCRIPTION.value:
                    pass
                else:
                    return True

    # Log unauthorized attempt
    audit_service.log_event(
        db=db,
        action=AuditAction.UNAUTHORIZED_ACCESS_ATTEMPT,
        resource_type="document",
        actor_id=user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
        ip_address=client_ip,
        details=f"Unauthorized access attempt to document {doc.id} by user {user.id}",
    )
    raise PermissionDeniedException("You are not authorized to view or download this patient's medical document.")


@router.post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form(DocumentType.OTHER.value),
    clinical_date: Optional[str] = Form(None),
    patient_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Securely upload a medical record (Prescription, Lab Report, Discharge Summary, Scan).
    Hashed with SHA-256 and stored in an isolated vault.
    """
    client_ip = request.client.host if request.client else None

    # Determine target patient
    target_patient_id: str
    if current_user.role == UserRole.PATIENT.value:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            raise PermissionDeniedException("No patient profile associated with this account")
        target_patient_id = patient.id
    else:
        # Doctor or Admin uploading on behalf of a patient
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id is required when uploading as doctor or admin",
            )
        target_patient_id = patient_id

    # Parse clinical date if supplied
    parsed_date: Optional[date] = None
    if clinical_date:
        try:
            parsed_date = datetime.strptime(clinical_date, "%Y-%m-%d").date()
        except ValueError:
            parsed_date = None

    # Persist file securely
    rel_path, orig_filename, file_size, sha256_hash = await storage_service.save_patient_document(
        patient_id=target_patient_id,
        file=file,
    )

    doc = MedicalDocument(
        patient_id=target_patient_id,
        uploader_id=current_user.id,
        title=title,
        document_type=document_type,
        file_path=rel_path,
        file_name=orig_filename,
        file_size=file_size,
        mime_type=file.content_type or "application/octet-stream",
        sha256_hash=sha256_hash,
        status=DocumentStatus.UPLOADED.value,
        clinical_date=parsed_date,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    audit_service.log_event(
        db=db,
        action=AuditAction.UPLOAD_DOCUMENT,
        resource_type="document",
        actor_id=current_user.id,
        patient_id=target_patient_id,
        resource_id=doc.id,
        ip_address=client_ip,
        details=f"Document uploaded: {orig_filename} ({file_size} bytes, type: {document_type})",
    )

    return DocumentUploadResponse(
        message="Medical document securely stored and registered",
        document=DocumentResponse.model_validate(doc),
    )


@router.get("", response_model=list[DocumentResponse])
def list_documents(
    request: Request,
    patient_id: Optional[str] = None,
    document_type: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    List medical documents.
    Patients can only see their own records.
    Doctors must specify a patient_id and have active patient consent.
    """
    query = db.query(MedicalDocument)

    if current_user.role == UserRole.PATIENT.value:
        patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
        if not patient:
            return []
        query = query.filter(MedicalDocument.patient_id == patient.id)
    elif current_user.role == UserRole.DOCTOR.value:
        if not patient_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="patient_id parameter is required for doctor record retrieval",
            )
        # Check active consent
        doctor = db.query(Doctor).filter(Doctor.user_id == current_user.id).first()
        if not doctor:
            raise PermissionDeniedException("Doctor profile missing")
        now = datetime.utcnow()
        active_grant = (
            db.query(ConsentGrant)
            .filter(
                ConsentGrant.patient_id == patient_id,
                ConsentGrant.doctor_id == doctor.id,
                ConsentGrant.is_revoked == False,
                ConsentGrant.valid_from <= now,
                ConsentGrant.valid_until >= now,
            )
            .first()
        )
        if not active_grant:
            raise PermissionDeniedException("No active consent grant found for this patient")
        query = query.filter(MedicalDocument.patient_id == patient_id)
        if active_grant.scope == "prescriptions_only":
            query = query.filter(MedicalDocument.document_type == DocumentType.PRESCRIPTION.value)
        elif active_grant.scope == "labs_only":
            query = query.filter(MedicalDocument.document_type == DocumentType.LAB_REPORT.value)
    elif current_user.role == UserRole.ADMIN.value:
        if patient_id:
            query = query.filter(MedicalDocument.patient_id == patient_id)

    if document_type:
        query = query.filter(MedicalDocument.document_type == document_type)

    docs = query.order_by(MedicalDocument.created_at.desc()).all()
    return [DocumentResponse.model_validate(d) for d in docs]


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_metadata(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Retrieve metadata for a specific document with authorization enforcement."""
    doc = db.query(MedicalDocument).filter(MedicalDocument.id == document_id).first()
    if not doc:
        raise ResourceNotFoundException("Medical Document")

    _verify_document_access(current_user, doc, db, request)

    client_ip = request.client.host if request.client else None
    audit_service.log_event(
        db=db,
        action=AuditAction.VIEW_RECORD,
        resource_type="document",
        actor_id=current_user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
        ip_address=client_ip,
        details=f"Viewed metadata for document: {doc.title}",
    )

    return DocumentResponse.model_validate(doc)


@router.get("/{document_id}/download")
def download_document(
    document_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Download/stream the verified binary file for an authorized user."""
    doc = db.query(MedicalDocument).filter(MedicalDocument.id == document_id).first()
    if not doc:
        raise ResourceNotFoundException("Medical Document")

    _verify_document_access(current_user, doc, db, request)

    file_path = storage_service.get_secure_file_path(doc.file_path)

    client_ip = request.client.host if request.client else None
    audit_service.log_event(
        db=db,
        action=AuditAction.DOWNLOAD_DOCUMENT,
        resource_type="document",
        actor_id=current_user.id,
        patient_id=doc.patient_id,
        resource_id=doc.id,
        ip_address=client_ip,
        details=f"Downloaded file: {doc.file_name}",
    )

    return FileResponse(
        path=str(file_path),
        filename=doc.file_name,
        media_type=doc.mime_type,
    )
