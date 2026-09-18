from sqlalchemy import Column, String, DateTime, ForeignKey, Text, JSON
from datetime import datetime, timezone
import uuid
from app.db.base import Base

def gen_uuid():
    return str(uuid.uuid4())

class EHRSource(Base):
    __tablename__ = "ehr_sources"

    id = Column(String(64), primary_key=True) # e.g. src-city-general
    name = Column(String(255), nullable=False) # City General Hospital
    protocol = Column(String(64), nullable=False) # FHIR, HL7 v2, Custom API, NCPDP
    format = Column(String(64), nullable=False) # JSON, HL7-ER7, CSV/JSON
    endpoint_url = Column(String(512), nullable=True)
    auth_type = Column(String(64), default="mTLS")
    status = Column(String(32), default="Connected") # Connected, Temporarily Unavailable, Offline
    last_sync = Column(String(64), default="Just now")
    security_info = Column(String(128), default="Secure (mTLS)")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class EHRRecord(Base):
    __tablename__ = "ehr_records"

    id = Column(String(64), primary_key=True, default=gen_uuid)
    source_id = Column(String(64), ForeignKey("ehr_sources.id"), nullable=False)
    external_patient_id = Column(String(128), nullable=True, index=True)
    external_record_id = Column(String(128), nullable=True)
    patient_identifier = Column(String(128), nullable=True, index=True)
    format = Column(String(32), nullable=False) # FHIR, HL7, CSV, JSON
    raw_payload = Column(Text, nullable=False)
    normalized_payload = Column(JSON, nullable=False)
    ingested_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
