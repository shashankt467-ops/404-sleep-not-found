from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def gen_uuid():
    return str(uuid.uuid4())

class Patient(Base):
    __tablename__ = "patients"

    # Cryptographically secure, unpredictable non-sequential ID format: HC04-PAT-XXXX-XXXX
    id = Column(String(64), primary_key=True)
    full_name = Column(String(255), nullable=False, index=True)
    dob = Column(String(32), nullable=False) # e.g. 14/02/2004 or 1990-05-12
    sex = Column(String(32), nullable=True)
    phone = Column(String(64), nullable=True, index=True)
    emergency_contact = Column(String(255), nullable=True)
    blood_group = Column(String(16), nullable=True, default="Unknown")
    allergies = Column(Text, nullable=True) # JSON or comma-separated
    existing_conditions = Column(Text, nullable=True)
    address = Column(Text, nullable=True)
    email = Column(String(255), nullable=True)
    previous_hospital = Column(String(255), nullable=True)
    insurance_info = Column(String(255), nullable=True)
    priority = Column(String(32), default="MEDIUM PRIORITY") # CRITICAL, HIGH PRIORITY, MEDIUM PRIORITY, LOW PRIORITY
    status = Column(String(32), default="Active")
    registered_by_doctor_id = Column(String(64), ForeignKey("users.id"), nullable=True)
    primary_org_id = Column(String(64), ForeignKey("organizations.id"), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    records = relationship("MedicalRecord", back_populates="patient", cascade="all, delete-orphan")
    otps = relationship("PatientAccessOtp", back_populates="patient", cascade="all, delete-orphan")
    doctor_relationships = relationship("DoctorPatientRelationship", back_populates="patient")

class PatientAccessOtp(Base):
    __tablename__ = "patient_access_otps"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False)
    otp_code = Column(String(16), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", back_populates="otps")

class DoctorPatientRelationship(Base):
    __tablename__ = "doctor_patient_relationships"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    doctor_id = Column(String(64), ForeignKey("users.id"), nullable=False)
    patient_id = Column(String(64), ForeignKey("patients.id"), nullable=False)
    organization_id = Column(String(64), ForeignKey("organizations.id"), nullable=True)
    relationship_type = Column(String(64), default="TREATING_PHYSICIAN")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    patient = relationship("Patient", back_populates="doctor_relationships")
