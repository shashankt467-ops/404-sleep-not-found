from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class PatientCreateRequest(BaseModel):
    full_name: str
    dob: str
    sex: Optional[str] = "Unknown"
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    blood_group: Optional[str] = "Unknown"
    allergies: Optional[List[str]] = []
    existing_conditions: Optional[List[str]] = []
    address: Optional[str] = None
    email: Optional[str] = None
    previous_hospital: Optional[str] = None
    insurance_info: Optional[str] = None
    priority: Optional[str] = "MEDIUM PRIORITY"
    initial_notes: Optional[str] = None

class PatientResponse(BaseModel):
    id: str
    full_name: str
    dob: str
    sex: Optional[str] = None
    phone: Optional[str] = None
    emergency_contact: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: List[str] = []
    existing_conditions: List[str] = []
    priority: str
    status: str
    qr_token: str
    created_at: datetime

    class Config:
        from_attributes = True

class PatientSearchQuery(BaseModel):
    query: str # patient ID, name, or token
    dob: Optional[str] = None
    phone: Optional[str] = None
