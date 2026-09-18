from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class EHRQueryRequest(BaseModel):
    patient_id: str
    purpose: Optional[str] = "Emergency Treatment"
    emergency_case_id: Optional[str] = None

class EHRSourceStatus(BaseModel):
    id: str
    name: str
    protocol: str
    format: str
    status: str
    sync: str
    security: str

class EHRRecordItem(BaseModel):
    source: str
    format: str
    updated: str
    fields: Dict[str, Any]

class EHRQueryResponse(BaseModel):
    patient_id: str
    sources_queried: int
    successful_sources: int
    failed_sources: List[str] = []
    records: List[EHRRecordItem]
    query_status: str

class EHRImportRequest(BaseModel):
    source_name: str
    format: str # FHIR, HL7, CSV, JSON
    payload: str
    patient_hint_id: Optional[str] = None
