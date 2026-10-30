from datetime import datetime, date
from typing import Optional
from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    id: str
    patient_id: str
    uploader_id: str
    title: str
    document_type: str
    file_name: str
    file_size: int
    mime_type: str
    sha256_hash: str
    status: str
    clinical_date: Optional[date] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    message: str
    document: DocumentResponse
