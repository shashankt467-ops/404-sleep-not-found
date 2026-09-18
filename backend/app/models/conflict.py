from sqlalchemy import Column, String, DateTime, ForeignKey, Text
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def gen_uuid():
    return str(uuid.uuid4())

class Conflict(Base):
    __tablename__ = "conflicts"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    field_name = Column(String(128), nullable=False) # e.g. Allergy, Blood Group, Medication, Diagnosis
    severity = Column(String(32), nullable=False) # critical, high, medium, low
    
    # Source A details
    source_a = Column(String(255), nullable=False)
    value_a = Column(Text, nullable=False)
    date_a = Column(String(64), nullable=True)
    record_id_a = Column(String(64), nullable=True)
    
    # Source B details
    source_b = Column(String(255), nullable=False)
    value_b = Column(Text, nullable=False)
    date_b = Column(String(64), nullable=True)
    record_id_b = Column(String(64), nullable=True)
    
    status = Column(String(32), default="UNRESOLVED") # UNRESOLVED, RESOLVED
    resolution_notes = Column(Text, nullable=True)
    resolved_by = Column(String(255), nullable=True) # Clinician
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)
