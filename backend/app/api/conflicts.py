from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Dict, Any

from app.db.session import get_db
from app.core.zero_trust import get_current_verified_professional, evaluate_zero_trust_access
from app.core.audit_logger import record_audit
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.ehr_source import EHRRecord, EHRSource
from app.models.conflict import Conflict
from app.schemas.conflict import ConflictResponse, ConflictResolveRequest, ConflictSourceDetail
from app.integrations.canonical import CanonicalMedicalRecord, CanonicalAllergy, CanonicalMedication
from app.services.conflict_detector import detect_medical_conflicts

router = APIRouter(tags=["Conflict Detection"])

@router.get("/patients/{id}/conflicts", response_model=List[ConflictResponse])
def get_patient_conflicts(
    id: str,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Detects and returns clinical conflicts across all connected sources for patient.
    Evaluates blood groups, allergies (Critical), and anticoagulant medications.
    """
    patient = db.query(Patient).filter(Patient.id == id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    evaluate_zero_trust_access(db, current_user, patient.id, purpose="Conflict Detection")

    # Load stored EHR records for this patient
    ehr_records = db.query(EHRRecord).filter(EHRRecord.patient_identifier == patient.id).all()
    canonical_records = []
    
    for r in ehr_records:
        src = db.query(EHRSource).filter(EHRSource.id == r.source_id).first()
        src_name = src.name if src else "External Hospital"
        payload = r.normalized_payload
        
        c = CanonicalMedicalRecord(
            source_name=src_name,
            format=r.format,
            patient_id=patient.id,
            full_name=payload.get("name") or patient.full_name,
            dob=payload.get("dob") or patient.dob,
            blood_group=payload.get("bloodGroup") or payload.get("blood_group")
        )
        for a in payload.get("allergies", []):
            sub = a if isinstance(a, str) else a.get("substance", "")
            c.allergies.append(CanonicalAllergy(substance=sub, source_system=src_name))
        for m in payload.get("medications", []):
            name = m if isinstance(m, str) else m.get("name", "")
            c.medications.append(CanonicalMedication(name=name, source_system=src_name))
        canonical_records.append(c)

    # Check for recorded conflicts in DB
    existing_conflicts = db.query(Conflict).filter(Conflict.patient_id == patient.id).all()
    
    # Run dynamic detection
    detected = detect_medical_conflicts(patient.id, canonical_records)

    # Sync into DB if not present
    for d in detected:
        exists = any(ec.field_name == d["field"] for ec in existing_conflicts)
        if not exists:
            new_c = Conflict(
                id=d["id"],
                patient_id=patient.id,
                field_name=d["field"],
                severity=d["severity"],
                source_a=d["a"]["source"],
                value_a=d["a"]["value"],
                date_a=d["a"]["date"],
                source_b=d["b"]["source"],
                value_b=d["b"]["value"],
                date_b=d["b"]["date"],
                status="UNRESOLVED"
            )
            db.add(new_c)
    db.commit()

    # Query all active conflicts
    all_conflicts = db.query(Conflict).filter(Conflict.patient_id == patient.id).all()
    results = []
    for c in all_conflicts:
        results.append(ConflictResponse(
            id=c.id,
            patient_id=c.patient_id,
            field=c.field_name,
            severity=c.severity,
            a=ConflictSourceDetail(source=c.source_a, value=c.value_a, date=c.date_a or "Recent"),
            b=ConflictSourceDetail(source=c.source_b, value=c.value_b, date=c.date_b or "Recent"),
            status=c.status,
            clinical_advisory=f"⚠ Conflict detected on {c.field_name}. Clinical verification required."
        ))

    record_audit(
        db=db, user_id=current_user.id,
        user_name=current_user.professional_profile.full_name if current_user.professional_profile else current_user.email,
        role=current_user.role.value, action="CONFLICT_VIEWED",
        patient_id=patient.id, result="Allowed",
        details={"conflicts_detected": len(results)}
    )

    return results

@router.post("/conflicts/{id}/resolve")
def resolve_conflict(
    id: str,
    req: ConflictResolveRequest,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Clinician resolves a conflict after verifying clinical evidence.
    Updates conflict status and records justification in permanent audit log.
    """
    conflict = db.query(Conflict).filter(Conflict.id == id).first()
    if not conflict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conflict record not found.")

    prof = current_user.professional_profile
    resolver_name = prof.full_name if prof else current_user.email

    conflict.status = "RESOLVED"
    conflict.resolved_by = resolver_name
    conflict.resolution_notes = f"Selected: '{req.selected_value}'. Justification: {req.resolution_notes}"
    conflict.resolved_at = datetime.now(timezone.utc)
    db.commit()

    record_audit(
        db=db, user_id=current_user.id, user_name=resolver_name,
        role=current_user.role.value, action="CONFLICT_RESOLVED",
        patient_id=conflict.patient_id, purpose="Clinical Resolution",
        result="Allowed", details={"conflict_id": conflict.id, "selected_value": req.selected_value, "notes": req.resolution_notes}
    )

    return {"message": "Conflict successfully marked as clinically resolved.", "conflict_id": conflict.id}
