from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class CanonicalAllergy(BaseModel):
    substance: str
    status: str = "active" # active, resolved, refuted
    severity: Optional[str] = "moderate" # mild, moderate, severe, fatal
    reaction: Optional[str] = None
    recorded_date: Optional[str] = None
    source_system: str

class CanonicalMedication(BaseModel):
    name: str
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    route: Optional[str] = None
    status: str = "active"
    start_date: Optional[str] = None
    source_system: str

class CanonicalCondition(BaseModel):
    code: Optional[str] = None
    display_name: str
    clinical_status: str = "active"
    verification_status: str = "confirmed"
    onset_date: Optional[str] = None
    source_system: str

class CanonicalObservation(BaseModel):
    test_name: str
    value: str
    unit: Optional[str] = None
    reference_range: Optional[str] = None
    interpretation: Optional[str] = None # Normal, High, Critical
    effective_date: Optional[str] = None
    source_system: str

class CanonicalProcedure(BaseModel):
    procedure_name: str
    performed_date: Optional[str] = None
    outcome: Optional[str] = None
    source_system: str

class CanonicalMedicalRecord(BaseModel):
    external_id: Optional[str] = None
    source_name: str
    format: str
    patient_id: Optional[str] = None
    full_name: Optional[str] = None
    dob: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: List[CanonicalAllergy] = []
    medications: List[CanonicalMedication] = []
    conditions: List[CanonicalCondition] = []
    observations: List[CanonicalObservation] = []
    procedures: List[CanonicalProcedure] = []
    recent_events: List[str] = []
    raw_payload: Optional[str] = None
    ingested_at: datetime = Field(default_factory=datetime.utcnow)
