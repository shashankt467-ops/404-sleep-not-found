from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean, Integer, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid
from app.db.base import Base

def gen_uuid():
    return str(uuid.uuid4())

class RecordType(str, enum.Enum):
    DIAGNOSIS = "Diagnosis"
    ALLERGY = "Allergy"
    MEDICATION = "Medication"
    PROCEDURE = "Procedure"
    SURGERY = "Surgery"
    LAB_RESULT = "Laboratory Result"
    VITAL_SIGNS = "Vital Signs"
    EMERGENCY_VISIT = "Emergency Visit"
    DISCHARGE_SUMMARY = "Discharge Summary"
    CLINICAL_NOTE = "Clinical Note"

class MedicalRecord(Base):
    __tablename__ = "medical_records"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False, index=True)
    provider_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    organization_id = Column(String(64), ForeignKey("organizations.id"), nullable=True)
    record_type = Column(String(64), nullable=False) # e.g. RecordType value
    clinical_data = Column(JSON, nullable=False) # Structured payload (title, value, severity, unit, date, notes)
    source = Column(String(255), nullable=False) # Hospital/source name
    author = Column(String(255), nullable=True) # Clinician name
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", back_populates="records")
    versions = relationship("RecordVersion", back_populates="record", cascade="all, delete-orphan", order_by="RecordVersion.version_num.desc()")

class RecordVersion(Base):
    __tablename__ = "record_versions"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    record_id = Column(String(64), ForeignKey("medical_records.id"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False, default=1)
    previous_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=False)
    changed_by = Column(String(255), nullable=False) # Clinician ID or Name
    reason = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    record = relationship("MedicalRecord", back_populates="versions")
