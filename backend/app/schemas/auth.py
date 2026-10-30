from datetime import date
from typing import Optional, Literal
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=72)
    full_name: str = Field(..., min_length=2, max_length=255)
    role: Literal["patient", "doctor"] = "patient"
    phone: Optional[str] = Field(default=None, max_length=50)
    
    # Optional Doctor fields
    license_number: Optional[str] = Field(default=None, max_length=100)
    specialization: Optional[str] = Field(default=None, max_length=100)
    hospital_affiliation: Optional[str] = Field(default=None, max_length=200)
    
    # Optional Patient fields
    date_of_birth: Optional[date] = None
    gender: Optional[str] = Field(default=None, max_length=20)
    blood_group: Optional[str] = Field(default=None, max_length=10)
    emergency_contact: Optional[str] = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def password_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes")
        return value


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: str
    full_name: str
    email: str


class UserOut(BaseModel):
    id: str
    email: str
    full_name: str
    role: str
    phone: Optional[str] = None
    is_active: bool
    
    model_config = ConfigDict(from_attributes=True)
