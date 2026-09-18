from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class ConflictSourceDetail(BaseModel):
    source: str
    value: str
    date: str

class ConflictResponse(BaseModel):
    id: str
    patient_id: str
    field: str
    severity: str # critical, high, medium, low
    a: ConflictSourceDetail
    b: ConflictSourceDetail
    status: str
    clinical_advisory: str

class ConflictResolveRequest(BaseModel):
    selected_value: str
    resolution_notes: str
