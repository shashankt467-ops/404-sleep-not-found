from sqlalchemy import Column, String, DateTime, ForeignKey, Boolean, JSON
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def gen_uuid():
    return str(uuid.uuid4())

class ConsentPolicy(Base):
    __tablename__ = "consent_policies"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False)
    granted_to_role = Column(String(64), nullable=False) # DOCTOR, EMT, ALL
    purpose = Column(String(128), default="EMERGENCY_TREATMENT")
    data_scope = Column(JSON, nullable=True) # ["ALLERGIES", "MEDICATIONS", "CONDITIONS", "LABS"]
    is_active = Column(Boolean, default=True)
    start_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expiry_time = Column(DateTime, nullable=True)
