from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from app.models.user import UserRole, AccountStatus

class DoctorRegisterRequest(BaseModel):
    full_name: str
    dob: Optional[str] = None
    reg_number: str # e.g. MED-8829104
    licensing_authority: str
    hospital_name: str
    department: str
    email: EmailStr
    phone: str
    password: str
    id_proof: Optional[str] = None
    credentials_file: Optional[str] = None

class EMTRegisterRequest(BaseModel):
    full_name: str
    emt_id: str # e.g. EMT-44029
    organization: str
    emergency_service: str
    email: EmailStr
    phone: str
    password: str
    credentials_file: Optional[str] = None

class DisasterResponseRegisterRequest(BaseModel):
    full_name: str
    organization: str
    role_title: str
    org_id: str
    email: EmailStr
    phone: str
    password: str
    authorization_info: Optional[str] = None

class LoginRequest(BaseModel):
    email: str # email or professional id or patient id
    password: str
    role_hint: Optional[str] = None
    auth_method: Optional[str] = "token" # token, biometric, emergency

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    user_name: str
    email: str
    role: str
    account_status: str
    hospital: Optional[str] = None
    permissions: List[str] = []

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class PatientAccessRequest(BaseModel):
    patient_id: str

class PatientVerifyOtpRequest(BaseModel):
    patient_id: str
    otp_code: str
