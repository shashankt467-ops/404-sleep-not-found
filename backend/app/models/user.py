from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum
import uuid
from app.db.base import Base

class UserRole(str, enum.Enum):
    DOCTOR = "DOCTOR"
    EMT = "EMT"
    DISASTER_RESPONSE = "DISASTER_RESPONSE"
    ADMIN = "ADMIN"
    PATIENT = "PATIENT"

class AccountStatus(str, enum.Enum):
    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    SUSPENDED = "SUSPENDED"

def gen_uuid():
    return str(uuid.uuid4())

class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    name = Column(String(255), nullable=False, unique=True)
    org_type = Column(String(64), nullable=False, default="Hospital")  # Hospital, Clinic, Trauma Center, Lab, Pharmacy
    registration_info = Column(String(255), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(64), nullable=True)
    status = Column(String(32), default="ACTIVE")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    professionals = relationship("Professional", back_populates="organization")

class User(Base):
    __tablename__ = "users"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(64), nullable=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(SQLEnum(UserRole), nullable=False, default=UserRole.DOCTOR)
    account_status = Column(SQLEnum(AccountStatus), nullable=False, default=AccountStatus.PENDING_VERIFICATION)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    last_login = Column(DateTime, nullable=True)

    professional_profile = relationship("Professional", back_populates="user", uselist=False, foreign_keys="Professional.user_id")

class Professional(Base):
    __tablename__ = "professionals"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    user_id = Column(String(64), ForeignKey("users.id"), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    dob = Column(String(32), nullable=True)
    reg_number = Column(String(128), unique=True, index=True, nullable=False) # e.g. MED-8829104
    licensing_authority = Column(String(255), nullable=False)
    organization_id = Column(String(64), ForeignKey("organizations.id"), nullable=True)
    department = Column(String(128), nullable=True)
    professional_email = Column(String(255), nullable=True)
    phone = Column(String(64), nullable=True)
    id_proof = Column(String(255), nullable=True)
    credentials_file = Column(String(255), nullable=True)
    verification_status = Column(SQLEnum(AccountStatus), default=AccountStatus.PENDING_VERIFICATION)
    rejection_reason = Column(Text, nullable=True)
    verified_by = Column(String(64), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="professional_profile", foreign_keys=[user_id])
    organization = relationship("Organization", back_populates="professionals")
