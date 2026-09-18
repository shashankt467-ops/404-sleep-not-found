from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any
import json

from app.db.session import get_db
from app.core.config import settings
from app.core.zero_trust import get_current_verified_professional, evaluate_zero_trust_access
from app.core.audit_logger import record_audit
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord
from app.models.ehr_source import EHRRecord, EHRSource
from app.models.conflict import Conflict
from app.models.emergency import EmergencyCase, AccessSession
from app.schemas.emergency import (
    EmergencySummaryResponse, EmergencyAccessRequest,
    EmergencyAccessResponse
)
from app.integrations.canonical import (
    CanonicalMedicalRecord, CanonicalAllergy, CanonicalMedication,
    CanonicalCondition, CanonicalObservation, CanonicalProcedure
)
from app.services.conflict_detector import detect_medical_conflicts
from app.services.emergency_synth import generate_emergency_summary

router = APIRouter(tags=["Emergency Interoperability"])

@router.post("/emergency-summary/{patient_id}", response_model=EmergencySummaryResponse)
def get_emergency_summary(
    patient_id: str,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Generate the official Emergency Medical Summary for an authorized clinician.
    Performs multi-source evidence extraction, conflict aggregation, and grounded AI synthesis.
    """
    patient = db.query(Patient).filter(Patient.id == patient_id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")

    access_eval = evaluate_zero_trust_access(db, current_user, patient.id, purpose="Emergency Treatment")

    # Load stored EHR records for this patient
    ehr_records = db.query(EHRRecord).filter(EHRRecord.patient_identifier == patient.id).all()
    canonical_records = []
    
    for r in ehr_records:
        src = db.query(EHRSource).filter(EHRSource.id == r.source_id).first()
        src_name = src.name if src else "Hospital Network"
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
        for cond in payload.get("conditions", []):
            c_name = cond if isinstance(cond, str) else cond.get("name", "")
            c.conditions.append(CanonicalCondition(display_name=c_name, source_system=src_name))
        for proc in payload.get("surgeries", []):
            p_name = proc if isinstance(proc, str) else proc.get("name", "")
            c.procedures.append(CanonicalProcedure(procedure_name=p_name, source_system=src_name))
        for k, v in payload.get("labs", {}).items():
            c.observations.append(CanonicalObservation(test_name=k, value=str(v), source_system=src_name))
        
        canonical_records.append(c)

    # Always populate intake clinical data from patient registration and medical records
    pat_allergies = []
    if patient.allergies:
        try:
            parsed_al = json.loads(patient.allergies)
            if isinstance(parsed_al, list):
                pat_allergies = [a for a in parsed_al if a]
            elif isinstance(parsed_al, str):
                pat_allergies = [parsed_al]
        except Exception:
            pat_allergies = [patient.allergies]

    pat_conditions = []
    if patient.existing_conditions:
        try:
            parsed_cd = json.loads(patient.existing_conditions)
            if isinstance(parsed_cd, list):
                pat_conditions = [c for c in parsed_cd if c]
            elif isinstance(parsed_cd, str):
                pat_conditions = [parsed_cd]
        except Exception:
            pat_conditions = [patient.existing_conditions]

    intake_record = CanonicalMedicalRecord(
        source_name="Direct Clinical Intake",
        format="Intake Registration",
        patient_id=patient.id,
        full_name=patient.full_name,
        dob=patient.dob,
        blood_group=patient.blood_group
    )
    for a in pat_allergies:
        intake_record.allergies.append(CanonicalAllergy(substance=a, source_system="Direct Clinical Intake"))
    for c in pat_conditions:
        intake_record.conditions.append(CanonicalCondition(display_name=c, source_system="Direct Clinical Intake"))

    # Load any direct MedicalRecord entries from DB
    med_records = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient.id,
        MedicalRecord.is_active == True
    ).all()
    for mr in med_records:
        if mr.record_type == "Allergy" and mr.clinical_data.get("substance"):
            intake_record.allergies.append(CanonicalAllergy(substance=mr.clinical_data["substance"], source_system=mr.source))
        elif mr.record_type == "Medication" and mr.clinical_data.get("name"):
            intake_record.medications.append(CanonicalMedication(name=mr.clinical_data["name"], source_system=mr.source))
        elif mr.record_type == "Diagnosis" and mr.clinical_data.get("condition"):
            intake_record.conditions.append(CanonicalCondition(display_name=mr.clinical_data["condition"], source_system=mr.source))
        elif mr.record_type == "Emergency Visit":
            intake_record.recent_events.append(f"Emergency Visit: {mr.clinical_data.get('complaint', 'Triage')} — {mr.created_at.strftime('%d %b %Y')}")

    if not canonical_records or intake_record.allergies or intake_record.conditions or intake_record.medications:
        canonical_records.append(intake_record)

    # Detect conflicts
    conflicts = detect_medical_conflicts(patient.id, canonical_records)

    # Find associated emergency case if any
    em_case = db.query(EmergencyCase).filter(EmergencyCase.patient_id == patient.id).first()
    case_num = em_case.case_number if em_case else f"EMG-2026-{patient.id[-4:]}"
    assigned = em_case.assigned_team if em_case else "Trauma Team A"

    summary = generate_emergency_summary(
        patient=patient,
        records=canonical_records,
        conflicts=conflicts,
        case_id=case_num,
        assigned_team=assigned
    )

    prof = current_user.professional_profile
    user_name = prof.full_name if prof else current_user.email

    record_audit(
        db=db, user_id=current_user.id, user_name=user_name,
        role=current_user.role.value, action="EMERGENCY_SUMMARY_GENERATED",
        patient_id=patient.id, purpose="Emergency Treatment",
        result="Allowed", emergency_status="Break-Glass" if access_eval.get("break_glass") else "Normal",
        details={"case_id": case_num, "conflicts": len(conflicts)}
    )

    return summary

@router.post("/emergency/access", response_model=EmergencyAccessResponse)
def activate_emergency_access(
    req: EmergencyAccessRequest,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Break-Glass Emergency Access Activation:
    Creates a temporary 15-minute expiring override session.
    Permanently recorded in the audit trail. Never an unrestricted bypass.
    """
    patient = db.query(Patient).filter(Patient.id == req.patient_id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    duration_mins = settings.EMERGENCY_SESSION_DURATION_MINUTES
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(minutes=duration_mins)

    # Invalidate previous sessions
    db.query(AccessSession).filter(
        AccessSession.patient_id == patient.id,
        AccessSession.requester_id == current_user.id
    ).update({"is_active": False})

    session = AccessSession(
        requester_id=current_user.id,
        patient_id=patient.id,
        purpose=f"Break-Glass Emergency Access: {req.reason}",
        case_id=req.case_id or f"EMG-{patient.id[-4:]}",
        break_glass=req.break_glass,
        start_time=now,
        expiry_time=expiry,
        is_active=True,
        records_accessed=[]
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    prof = current_user.professional_profile
    user_name = prof.full_name if prof else current_user.email

    record_audit(
        db=db, user_id=current_user.id, user_name=user_name,
        role=current_user.role.value, action="BREAK_GLASS_ACTIVATED",
        patient_id=patient.id, purpose=req.reason,
        result="Allowed", emergency_status="Break-Glass Active",
        details={"session_id": session.id, "duration_minutes": duration_mins, "reason": req.reason}
    )

    return EmergencyAccessResponse(
        session_id=session.id,
        patient_id=patient.id,
        is_active=True,
        break_glass=req.break_glass,
        expires_in_seconds=duration_mins * 60,
        message=f"Emergency access activated. This action has been permanently logged in the audit trail. Session expires in {duration_mins} minutes."
    )

@router.post("/emergency/access/deactivate")
def deactivate_emergency_access(
    patient_id: str,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """Explicitly terminate an active emergency access session."""
    db.query(AccessSession).filter(
        AccessSession.patient_id == patient_id.strip().upper(),
        AccessSession.requester_id == current_user.id,
        AccessSession.is_active == True
    ).update({"is_active": False})
    db.commit()

    record_audit(
        db=db, user_id=current_user.id,
        user_name=current_user.professional_profile.full_name if current_user.professional_profile else current_user.email,
        role=current_user.role.value, action="BREAK_GLASS_DEACTIVATED",
        patient_id=patient_id, result="Allowed"
    )

    return {"message": "Emergency access session terminated."}

@router.get("/emergency-cases")
def list_emergency_cases(
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """List active emergency cases across response network."""
    cases = db.query(EmergencyCase).order_by(EmergencyCase.created_at.desc()).all()
    results = []
    for c in cases:
        p = db.query(Patient).filter(Patient.id == c.patient_id).first()
        results.append({
            "id": c.id,
            "case_number": c.case_number,
            "patient_id": c.patient_id,
            "patient_name": p.full_name if p else "Unknown",
            "priority": c.priority,
            "status": c.status,
            "assigned_team": c.assigned_team,
            "created_at": c.created_at.strftime("%d %b %Y, %H:%M")
        })
    return results
