from datetime import date
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from app.api.deps import get_db, get_current_user
from app.core.errors import PermissionDeniedException, ResourceNotFoundException
from app.models.user import User
from app.models.patient import Patient
from app.models.document import MedicalDocument, DocumentType
from app.models.audit import AuditAction
from app.schemas.document import DocumentResponse, DocumentUploadResponse
from app.services.storage_service import storage_service
from app.services.audit_service import audit_service
from app.services.authorization import permitted_types, require_document_access, document_filter

router = APIRouter(prefix="/documents", tags=["Medical Documents"])


def target_patient(db, user, supplied_id):
    if user.role == "patient":
        patient = db.query(Patient).filter(Patient.user_id == user.id).first()
        if not patient or (supplied_id and str(supplied_id) != patient.id):
            raise PermissionDeniedException("Cannot upload to another patient's record")
        return patient.id
    if not supplied_id:
        raise HTTPException(400, "patient_id is required for doctor uploads")
    return str(supplied_id)


@router.post("/upload", response_model=DocumentUploadResponse, status_code=201)
async def upload_document(
    request: Request, file: UploadFile = File(...),
    title: str = Form(..., min_length=1, max_length=255),
    document_type: DocumentType = Form(DocumentType.OTHER),
    clinical_date: date | None = Form(None), patient_id: UUID | None = Form(None),
    current_user: User = Depends(get_current_user), db: Session = Depends(get_db),
):
    title = title.strip()
    if not title:
        raise HTTPException(422, "Title cannot be blank")
    target = target_patient(db, current_user, patient_id)
    allowed = permitted_types(db, current_user, target, request, action="upload")
    if document_type.value not in allowed:
        raise PermissionDeniedException("Upload is outside the authorized document scope")
    if not db.get(Patient, target):
        raise ResourceNotFoundException("Patient")
    path, filename, size, checksum = await storage_service.save_patient_document(target, file)
    doc = MedicalDocument(patient_id=target, uploader_id=current_user.id, title=title,
                          document_type=document_type.value, file_path=path, file_name=filename,
                          file_size=size, mime_type=storage_service.mime_for(filename),
                          sha256_hash=checksum, status="uploaded", clinical_date=clinical_date)
    try:
        db.add(doc)
        db.flush()
        audit_service.log_event(db, AuditAction.UPLOAD_DOCUMENT, "document", actor_id=current_user.id,
                                patient_id=target, resource_id=doc.id, commit=False)
        db.commit()
        db.refresh(doc)
    except Exception:
        db.rollback()
        storage_service.delete_file(path)
        raise
    return DocumentUploadResponse(message="Medical document securely stored and registered",
                                  document=DocumentResponse.model_validate(doc))


@router.get("", response_model=list[DocumentResponse])
def list_documents(request: Request, patient_id: UUID | None = None, document_type: DocumentType | None = None,
                   limit: int = 100, offset: int = 0,
                   current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not 1 <= limit <= 200 or offset < 0:
        raise HTTPException(422, "Invalid pagination")
    if current_user.role == "patient":
        profile = current_user.patient_profile
        if not profile:
            raise PermissionDeniedException("Patient profile missing")
        if patient_id and str(patient_id) != profile.id:
            raise PermissionDeniedException("Cannot list another patient's records")
        target = profile.id
    elif patient_id:
        target = str(patient_id)
    else:
        raise PermissionDeniedException("Patient authorization required")
    allowed = permitted_types(db, current_user, target, request)
    query = db.query(MedicalDocument).filter(MedicalDocument.patient_id == target,
                                            MedicalDocument.document_type.in_(allowed),
                                            document_filter(db, current_user, target))
    if document_type:
        query = query.filter(MedicalDocument.document_type == document_type.value)
    docs = query.order_by(MedicalDocument.created_at.desc(), MedicalDocument.id).offset(offset).limit(limit).all()
    audit_service.log_event(db, AuditAction.VIEW_RECORD, "document_list", actor_id=current_user.id, patient_id=target)
    return docs


def authorized_document(db, user, document_id, request):
    doc = db.get(MedicalDocument, str(document_id))
    if not doc:
        raise ResourceNotFoundException("Medical Document")
    require_document_access(db, user, doc, request)
    return doc


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document_metadata(document_id: UUID, request: Request,
                          current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = authorized_document(db, current_user, document_id, request)
    audit_service.log_event(db, AuditAction.VIEW_RECORD, "document", actor_id=current_user.id,
                            patient_id=doc.patient_id, resource_id=doc.id)
    return doc


@router.get("/{document_id}/download")
def download_document(document_id: UUID, request: Request,
                      current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    doc = authorized_document(db, current_user, document_id, request)
    path = storage_service.get_secure_file_path(doc.file_path, doc.sha256_hash)
    audit_service.log_event(db, AuditAction.DOWNLOAD_DOCUMENT, "document", actor_id=current_user.id,
                            patient_id=doc.patient_id, resource_id=doc.id)
    return FileResponse(path, filename=doc.file_name, media_type=doc.mime_type,
                         headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
