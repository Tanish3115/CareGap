from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class PatientProfile(BaseModel):
    id: str
    user_id: str
    full_name: str
    email: str
    phone: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    blood_group: Optional[str] = None
    emergency_contact: Optional[str] = None
    address: Optional[str] = None
    abha_id: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientProfileUpdate(BaseModel):
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=20)
    blood_group: Optional[str] = Field(default=None, max_length=10)
    emergency_contact: Optional[str] = Field(default=None, max_length=100)
    address: Optional[str] = Field(default=None, max_length=2000)
    abha_id: Optional[str] = Field(default=None, max_length=50)
