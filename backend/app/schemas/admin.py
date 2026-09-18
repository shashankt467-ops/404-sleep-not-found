from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ProfessionalVerificationItem(BaseModel):
    id: str
    user_id: str
    full_name: str
    role: str
    reg_number: str
    licensing_authority: str
    organization_name: str
    department: Optional[str] = None
    email: str
    phone: Optional[str] = None
    verification_status: str
    credentials_file: Optional[str] = None
    created_at: datetime
    rejection_reason: Optional[str] = None

class VerificationActionRequest(BaseModel):
    action: str # VERIFY, REJECT, SUSPEND
    rejection_reason: Optional[str] = None

class OrganizationResponse(BaseModel):
    id: str
    name: str
    org_type: str
    registration_info: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    status: str
    created_at: datetime
