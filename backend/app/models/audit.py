from sqlalchemy import Column, String, DateTime, Text, JSON
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def gen_uuid():
    return str(uuid.uuid4())

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    user_id = Column(String(64), nullable=True, index=True)
    user_name = Column(String(255), nullable=False)
    role = Column(String(64), nullable=False) # Physician, EMT, Disaster Response, Patient, Admin
    patient_id = Column(String(64), nullable=True, index=True)
    action = Column(String(128), nullable=False) # LOGIN, PATIENT_CREATED, QUERY, BREAK_GLASS, etc.
    purpose = Column(String(255), nullable=True) # Emergency Treatment, Direct Care, Audit
    result = Column(String(32), default="Allowed") # Allowed, Denied, Flagged
    emergency_status = Column(String(32), default="Normal") # Normal, Emergency Active, Break-Glass
    ip_address = Column(String(64), nullable=True)
    details = Column(JSON, nullable=True)
