from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from datetime import datetime

class CriticalFieldSummary(BaseModel):
    value: Any
    source: str
    updated: str
    confidence: str

class EmergencySummaryResponse(BaseModel):
    patient_id: str
    patient_name: str
    dob: str
    priority: str
    status: str
    case_id: str
    assigned: str
    blood_group: CriticalFieldSummary
    allergies: CriticalFieldSummary
    medications: CriticalFieldSummary
    conditions: CriticalFieldSummary
    surgeries: CriticalFieldSummary
    labs: Dict[str, str]
    recent_events: List[str]
    conflicts_count: int
    critical_conflicts: List[str] = []
    ai_synthesis: str
    safety_disclaimer: str = "AI-assisted decision support — clinical verification required."
    sources_count: int
    match_confidence: float

class EmergencyAccessRequest(BaseModel):
    patient_id: str
    reason: str
    case_id: Optional[str] = None
    break_glass: bool = True

class EmergencyAccessResponse(BaseModel):
    session_id: str
    patient_id: str
    is_active: bool
    break_glass: bool
    expires_in_seconds: int
    message: str
