from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class MedicalRecordCreateRequest(BaseModel):
    record_type: str # Diagnosis, Allergy, Medication, Procedure, Surgery, Laboratory Result, Vital Signs, Emergency Visit, Discharge Summary, Clinical Note
    clinical_data: Dict[str, Any]
    source: Optional[str] = None
    author: Optional[str] = None

class MedicalRecordUpdateRequest(BaseModel):
    clinical_data: Dict[str, Any]
    reason: str # Required reason for clinical versioning

class RecordVersionResponse(BaseModel):
    version_num: int
    previous_value: Optional[Dict[str, Any]] = None
    new_value: Dict[str, Any]
    changed_by: str
    reason: Optional[str] = None
    timestamp: datetime

    class Config:
        from_attributes = True

class MedicalRecordResponse(BaseModel):
    id: str
    patient_id: str
    provider_id: Optional[str] = None
    organization_id: Optional[str] = None
    record_type: str
    clinical_data: Dict[str, Any]
    source: str
    author: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    versions: List[RecordVersionResponse] = []

    class Config:
        from_attributes = True
