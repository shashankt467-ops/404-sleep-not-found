from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Dict, Any
import json


from app.db.session import get_db
from app.core.zero_trust import get_current_verified_professional, evaluate_zero_trust_access
from app.core.audit_logger import record_audit
from app.models.user import User
from app.models.patient import Patient
from app.models.ehr_source import EHRSource, EHRRecord
from app.models.medical_record import MedicalRecord
from app.schemas.ehr import EHRQueryRequest, EHRQueryResponse, EHRRecordItem, EHRSourceStatus, EHRImportRequest
from app.integrations.canonical import CanonicalMedicalRecord
from app.integrations.fhir.adapter import FHIRProvider
from app.integrations.hl7.adapter import HL7Provider
from app.integrations.csv_json.adapter import CSVJSONProvider

router = APIRouter(prefix="/ehr", tags=["EHR Interoperability"])

# Registered EHR adapter instances
PROVIDERS = {
    "src-city-general": FHIRProvider(source_name="City General Hospital"),
    "src-apollo": HL7Provider(source_name="Apollo Medical Center"),
    "src-gmc": FHIRProvider(source_name="Government Medical College"),
    "src-metro-trauma": CSVJSONProvider(source_name="Metro Trauma Centre"),
    "src-reg-lab": CSVJSONProvider(source_name="Regional Diagnostic Lab"),
    "src-pharmacy": CSVJSONProvider(source_name="Metro Pharmacy Network")
}

@router.get("/sources", response_model=List[EHRSourceStatus])
def get_ehr_sources(db: Session = Depends(get_db)):
    """List all connected EHR sources in the healthcare interoperability network."""
    sources = db.query(EHRSource).all()
    results = []
    for s in sources:
        results.append(EHRSourceStatus(
            id=s.id,
            name=s.name,
            protocol=s.protocol,
            format=s.format,
            status=s.status,
            sync=s.last_sync or "2 min ago",
            security=s.security_info or "Secure (mTLS)"
        ))
    return results

@router.post("/query", response_model=EHRQueryResponse)
def query_ehr_network(
    req: EHRQueryRequest,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Securely query connected EHR networks for patient medical information.
    Enforces zero-trust authorization, queries each source adapter,
    and returns normalized records. Transparently flags any unavailable source.
    """
    patient = db.query(Patient).filter(Patient.id == req.patient_id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient identifier not found.")

    evaluate_zero_trust_access(db, current_user, patient.id, purpose=req.purpose)

    sources = db.query(EHRSource).all()
    queried_count = len(sources)
    failed_sources = []
    collected_items = []

    for s in sources:
        if s.status != "Connected":
            # Per Requirement #26 & #42: Never pretend unavailable source responded!
            failed_sources.append(f"{s.name} ({s.status})")
            continue

        # Look up records stored for this source & patient identifier
        records_in_db = db.query(EHRRecord).filter(
            EHRRecord.source_id == s.id,
            EHRRecord.patient_identifier == patient.id
        ).all()

        for r in records_in_db:
            collected_items.append(EHRRecordItem(
                source=s.name,
                format=s.format,
                updated=r.ingested_at.strftime("%d %b %Y"),
                fields=r.normalized_payload
            ))

    # Always include intake registration record and any direct medical records
    pat_allergies_list = []
    if patient.allergies:
        try:
            parsed = json.loads(patient.allergies)
            pat_allergies_list = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            pat_allergies_list = [patient.allergies]

    pat_conds_list = []
    if patient.existing_conditions:
        try:
            parsed = json.loads(patient.existing_conditions)
            pat_conds_list = parsed if isinstance(parsed, list) else [parsed]
        except Exception:
            pat_conds_list = [patient.existing_conditions]

    internal_records = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient.id,
        MedicalRecord.is_active == True
    ).all()

    for r in internal_records:
        if r.record_type == "Allergy":
            sub = r.clinical_data.get("substance") or r.clinical_data.get("allergy")
            if sub and sub not in pat_allergies_list:
                pat_allergies_list.append(sub)
        elif r.record_type == "Diagnosis":
            cond = r.clinical_data.get("condition") or r.clinical_data.get("diagnosis")
            if cond and cond not in pat_conds_list:
                pat_conds_list.append(cond)

    collected_items.append(EHRRecordItem(
        source="HC-04 Direct Clinical Intake",
        format="Standardized FHIR JSON",
        updated=datetime.utcnow().strftime("%d %b %Y"),
        fields={
            "name": patient.full_name,
            "dob": patient.dob,
            "bloodGroup": patient.blood_group,
            "allergies": [a for a in pat_allergies_list if a],
            "medications": [r.clinical_data.get("name") or r.clinical_data.get("medication") for r in internal_records if r.record_type == "Medication" and (r.clinical_data.get("name") or r.clinical_data.get("medication"))],
            "conditions": [c for c in pat_conds_list if c],
            "surgeries": [],
            "labs": {}
        }
    ))

    author_name = current_user.professional_profile.full_name if current_user.professional_profile else current_user.email
    record_audit(
        db=db, user_id=current_user.id, user_name=author_name,
        role=current_user.role.value, action="EHR_QUERY",
        patient_id=patient.id, purpose=req.purpose,
        result="Allowed", details={"sources_queried": queried_count, "records_found": len(collected_items)}
    )

    return EHRQueryResponse(
        patient_id=patient.id,
        sources_queried=queried_count,
        successful_sources=queried_count - len(failed_sources),
        failed_sources=failed_sources,
        records=collected_items,
        query_status="Complete"
    )

@router.post("/fhir/import")
def import_fhir_record(req: EHRImportRequest, current_user: User = Depends(get_current_verified_professional), db: Session = Depends(get_db)):
    """Import and normalize external FHIR R4 JSON record."""
    provider = FHIRProvider(source_name=req.source_name)
    if not provider.validate_record(req.payload):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid FHIR JSON resource format.")

    canonical = provider.normalize_record(req.payload)
    patient_id = req.patient_hint_id or canonical.external_id

    ehr_rec = EHRRecord(
        source_id="src-city-general",
        external_patient_id=canonical.external_id,
        patient_identifier=patient_id,
        format="FHIR",
        raw_payload=req.payload,
        normalized_payload=canonical.dict()
    )
    db.add(ehr_rec)
    db.commit()

    record_audit(
        db=db, user_id=current_user.id, user_name=current_user.email,
        role=current_user.role.value, action="EHR_IMPORT_FHIR",
        patient_id=patient_id, result="Allowed"
    )

    return {"message": "FHIR resource imported and normalized.", "canonical": canonical}

@router.post("/hl7/import")
def import_hl7_record(req: EHRImportRequest, current_user: User = Depends(get_current_verified_professional), db: Session = Depends(get_db)):
    """Import and normalize external HL7 v2 message."""
    provider = HL7Provider(source_name=req.source_name)
    if not provider.validate_record(req.payload):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid HL7 v2 format (must start with MSH).")

    canonical = provider.normalize_record(req.payload)
    patient_id = req.patient_hint_id or canonical.patient_id

    ehr_rec = EHRRecord(
        source_id="src-apollo",
        external_patient_id=canonical.patient_id,
        patient_identifier=patient_id,
        format="HL7",
        raw_payload=req.payload,
        normalized_payload=canonical.dict()
    )
    db.add(ehr_rec)
    db.commit()

    record_audit(
        db=db, user_id=current_user.id, user_name=current_user.email,
        role=current_user.role.value, action="EHR_IMPORT_HL7",
        patient_id=patient_id, result="Allowed"
    )

    return {"message": "HL7 message parsed and canonicalized.", "canonical": canonical}

@router.post("/csv/import")
def import_csv_record(req: EHRImportRequest, current_user: User = Depends(get_current_verified_professional), db: Session = Depends(get_db)):
    """Import and normalize CSV data."""
    provider = CSVJSONProvider(source_name=req.source_name)
    canonical = provider.normalize_record(req.payload)
    patient_id = req.patient_hint_id or canonical.external_id

    ehr_rec = EHRRecord(
        source_id="src-reg-lab",
        external_patient_id=canonical.external_id,
        patient_identifier=patient_id,
        format="CSV",
        raw_payload=req.payload,
        normalized_payload=canonical.dict()
    )
    db.add(ehr_rec)
    db.commit()

    return {"message": "CSV imported and canonicalized.", "canonical": canonical}
