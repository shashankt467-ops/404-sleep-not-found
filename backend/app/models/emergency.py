from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, JSON
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def gen_uuid():
    return str(uuid.uuid4())

class EmergencyCase(Base):
    __tablename__ = "emergency_cases"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    case_number = Column(String(64), unique=True, index=True, nullable=False) # e.g. EMG-2026-00124
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False)
    priority = Column(String(32), default="HIGH PRIORITY") # CRITICAL, HIGH PRIORITY, MEDIUM PRIORITY, LOW PRIORITY
    status = Column(String(32), default="Active") # Active, Resolved, Triaged
    assigned_team = Column(String(128), default="Trauma Team A")
    chief_complaint = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime, nullable=True)

class AccessSession(Base):
    __tablename__ = "access_sessions"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    requester_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False)
    purpose = Column(String(255), nullable=False) # e.g. Emergency Treatment, Break-Glass Emergency
    case_id = Column(String(64), nullable=True)
    break_glass = Column(Boolean, default=False)
    start_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expiry_time = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True)
    records_accessed = Column(JSON, nullable=True) # list of record IDs accessed during session
