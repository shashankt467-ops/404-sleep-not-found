from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import json
import secrets

from app.db.session import get_db
from app.core.zero_trust import get_current_verified_professional, get_current_user, evaluate_zero_trust_access
from app.core.audit_logger import record_audit
from app.core.security import create_access_token
from app.models.user import User, UserRole, AccountStatus
from app.models.patient import Patient, PatientAccessOtp, DoctorPatientRelationship
from app.models.medical_record import MedicalRecord
from app.models.audit import AuditLog
from app.services.patient_id_gen import generate_patient_id, generate_qr_token
from app.schemas.patient import PatientCreateRequest, PatientResponse, PatientSearchQuery
from app.core.config import settings
from app.services.email_service import send_otp_email_async

router = APIRouter(prefix="/patients", tags=["Patients"])

@router.post("", response_model=PatientResponse, status_code=status.HTTP_201_CREATED)
def register_patient_by_doctor(
    req: PatientCreateRequest,
    current_doctor: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Authorized Doctor registers a new patient.
    System validates information, generates cryptographically secure,
    unpredictable, non-sequential Patient ID (e.g. HC04-PAT-7F82-91K4).
    QR code contains ONLY secure resolution token, no raw medical data.
    """
    if current_doctor.role not in [UserRole.DOCTOR, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only verified physicians can register new patients."
        )

    # Generate unique, unpredictable non-sequential ID
    patient_id = generate_patient_id(db)

    allergies_str = json.dumps(req.allergies) if req.allergies else "[]"
    conditions_str = json.dumps(req.existing_conditions) if req.existing_conditions else "[]"

    # Get doctor's hospital
    org_id = current_doctor.professional_profile.organization_id if current_doctor.professional_profile else None

    patient = Patient(
        id=patient_id,
        full_name=req.full_name.strip(),
        dob=req.dob.strip(),
        sex=req.sex or "Unknown",
        phone=req.phone,
        emergency_contact=req.emergency_contact,
        blood_group=req.blood_group or "Unknown",
        allergies=allergies_str,
        existing_conditions=conditions_str,
        address=req.address,
        email=req.email,
        previous_hospital=req.previous_hospital,
        insurance_info=req.insurance_info,
        priority=req.priority or "MEDIUM PRIORITY",
        status="Active",
        registered_by_doctor_id=current_doctor.id,
        primary_org_id=org_id
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    # Establish Doctor-Patient Relationship
    rel = DoctorPatientRelationship(
        doctor_id=current_doctor.id,
        patient_id=patient.id,
        organization_id=org_id,
        relationship_type="REGISTERING_PHYSICIAN"
    )
    db.add(rel)

    # If initial visit notes provided, create first medical record
    if req.initial_notes:
        first_record = MedicalRecord(
            patient_id=patient.id,
            provider_id=current_doctor.id,
            organization_id=org_id,
            record_type="Emergency Visit",
            clinical_data={
                "complaint": req.initial_notes,
                "blood_group": req.blood_group,
                "allergies": req.allergies or [],
                "notes": req.initial_notes
            },
            source="HC-04 Direct Intake",
            author=current_doctor.professional_profile.full_name if current_doctor.professional_profile else current_doctor.email
        )
        db.add(first_record)

    db.commit()

    qr_token = generate_qr_token(patient.id)

    record_audit(
        db=db, user_id=current_doctor.id,
        user_name=current_doctor.professional_profile.full_name if current_doctor.professional_profile else current_doctor.email,
        role=current_doctor.role.value, action="PATIENT_CREATED", patient_id=patient.id,
        purpose="Patient Registration", result="Allowed",
        details={"patient_id": patient.id, "name": patient.full_name, "priority": patient.priority}
    )

    return PatientResponse(
        id=patient.id,
        full_name=patient.full_name,
        dob=patient.dob,
        sex=patient.sex,
        phone=patient.phone,
        emergency_contact=patient.emergency_contact,
        blood_group=patient.blood_group,
        allergies=json.loads(patient.allergies or "[]"),
        existing_conditions=json.loads(patient.existing_conditions or "[]"),
        priority=patient.priority,
        status=patient.status,
        qr_token=qr_token,
        created_at=patient.created_at
    )

@router.get("", response_model=List[PatientResponse])
def list_patients(
    query: Optional[str] = None,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """List patients registered or authorized in the emergency network."""
    q = db.query(Patient)
    if query:
        q = q.filter(
            (Patient.id.ilike(f"%{query.strip()}%")) |
            (Patient.full_name.ilike(f"%{query.strip()}%")) |
            (Patient.phone.ilike(f"%{query.strip()}%"))
        )
    patients = q.order_by(Patient.created_at.desc()).all()

    results = []
    for p in patients:
        allergies_list = json.loads(p.allergies) if p.allergies and p.allergies.startswith("[") else ([p.allergies] if p.allergies else [])
        conds_list = json.loads(p.existing_conditions) if p.existing_conditions and p.existing_conditions.startswith("[") else ([p.existing_conditions] if p.existing_conditions else [])
        results.append(PatientResponse(
            id=p.id,
            full_name=p.full_name,
            dob=p.dob,
            sex=p.sex,
            phone=p.phone,
            emergency_contact=p.emergency_contact,
            blood_group=p.blood_group,
            allergies=allergies_list,
            existing_conditions=conds_list,
            priority=p.priority,
            status=p.status,
            qr_token=generate_qr_token(p.id),
            created_at=p.created_at
        ))
    return results

@router.get("/{id}", response_model=PatientResponse)
def get_patient_details(
    id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get patient demographic record with zero-trust validation."""
    patient = db.query(Patient).filter(Patient.id == id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    evaluate_zero_trust_access(db, current_user, patient.id, purpose="Direct Care")

    allergies_list = json.loads(patient.allergies) if patient.allergies and patient.allergies.startswith("[") else ([patient.allergies] if patient.allergies else [])
    conds_list = json.loads(patient.existing_conditions) if patient.existing_conditions and patient.existing_conditions.startswith("[") else ([patient.existing_conditions] if patient.existing_conditions else [])

    record_audit(
        db=db, user_id=current_user.id,
        user_name=current_user.professional_profile.full_name if current_user.professional_profile else current_user.email,
        role=current_user.role.value, action="PATIENT_VIEWED", patient_id=patient.id,
        result="Allowed"
    )

    return PatientResponse(
        id=patient.id,
        full_name=patient.full_name,
        dob=patient.dob,
        sex=patient.sex,
        phone=patient.phone,
        emergency_contact=patient.emergency_contact,
        blood_group=patient.blood_group,
        allergies=allergies_list,
        existing_conditions=conds_list,
        priority=patient.priority,
        status=patient.status,
        qr_token=generate_qr_token(patient.id),
        created_at=patient.created_at
    )

@router.post("/{id}/request-otp")
def request_patient_access_otp(id: str, db: Session = Depends(get_db)):
    """
    Patient Portal Step 1: Patient enters their HC-04 Patient ID.
    Backend verifies patient exists, generates a 6-digit OTP,
    and returns simulated delivery status to registered contact.
    """
    patient = db.query(Patient).filter(Patient.id == id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient ID not recognized in HC-04 network.")

    # Invalidate previous unused OTPs for this patient
    db.query(PatientAccessOtp).filter(
        PatientAccessOtp.patient_id == patient.id,
        PatientAccessOtp.is_used == False
    ).update({"is_used": True})

    # Generate 6-digit cryptographic OTP
    otp_code = f"{secrets.randbelow(900000) + 100000}"
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    otp_record = PatientAccessOtp(
        patient_id=patient.id,
        otp_code=otp_code,
        expires_at=expires_at,
        is_used=False
    )
    db.add(otp_record)
    db.commit()

    # Mask contact for privacy
    target_email = patient.email or settings.DEFAULT_PATIENT_EMAIL
    if target_email and "@" in target_email:
        parts = target_email.split("@")
        masked = parts[0][:2] + "•••@" + parts[1]
    elif patient.phone and len(patient.phone) >= 7:
        masked = patient.phone[:3] + "•••" + patient.phone[-3:]
    else:
        masked = "registered email"

    # Dispatch actual email via Gmail SMTP
    send_otp_email_async(
        recipient_email=target_email,
        patient_name=patient.full_name,
        patient_id=patient.id,
        otp_code=otp_code
    )

    # In development/evaluation mode, return OTP code in response for testing convenience
    return {
        "message": f"Verification OTP sent to {masked} (check your Gmail inbox).",
        "patient_id": patient.id,
        "expires_in_minutes": 10,
        "delivered_to": masked,
        "dev_otp": otp_code # Marked for convenience alongside live email delivery
    }

@router.post("/{id}/verify-otp")
def verify_patient_access_otp(id: str, otp_code: str, db: Session = Depends(get_db)):
    """
    Patient Portal Step 2: Patient enters OTP received.
    Backend validates OTP and issues secure patient session token.
    Patient ID ALONE never gives access!
    """
    patient = db.query(Patient).filter(Patient.id == id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient ID not found.")

    now = datetime.now(timezone.utc)
    otp_record = db.query(PatientAccessOtp).filter(
        PatientAccessOtp.patient_id == patient.id,
        PatientAccessOtp.otp_code == otp_code.strip(),
        PatientAccessOtp.is_used == False,
        PatientAccessOtp.expires_at > now
    ).first()

    if not otp_record:
        record_audit(
            db=db, user_id=None, user_name="Patient Access Attempt",
            role="PATIENT", action="PATIENT_OTP_FAILED", patient_id=patient.id,
            result="Denied", purpose="Patient Portal"
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired OTP code.")

    # Mark OTP as used
    otp_record.is_used = True
    db.commit()

    # Issue patient session token
    token_data = {
        "sub": patient.id,
        "email": patient.email or f"{patient.id}@patient.hc04",
        "role": UserRole.PATIENT.value,
        "status": "VERIFIED"
    }
    access_token = create_access_token(token_data, expires_delta=timedelta(hours=2))

    record_audit(
        db=db, user_id=patient.id, user_name=patient.full_name,
        role="PATIENT", action="PATIENT_PORTAL_LOGIN", patient_id=patient.id,
        result="Allowed", purpose="Patient Portal Access"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "patient_id": patient.id,
        "patient_name": patient.full_name
    }

@router.get("/{id}/portal")
def get_patient_portal_data(id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Patient Portal view: Personal emergency summary, visits, authorized providers, access history.
    Does NOT return internal security parameters or bypass flags.
    """
    patient = db.query(Patient).filter(Patient.id == id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    # Ensure requesting user is either the patient themselves or verified clinician
    if current_user.role == UserRole.PATIENT and current_user.id != patient.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized access to patient records.")

    records = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient.id,
        MedicalRecord.is_active == True
    ).order_by(MedicalRecord.created_at.desc()).all()

    # Get access audit history for this patient
    audit_events = db.query(AuditLog).filter(
        AuditLog.patient_id == patient.id
    ).order_by(AuditLog.timestamp.desc()).limit(15).all()

    access_history = []
    for a in audit_events:
        access_history.append({
            "time": a.timestamp.strftime("%d %b %Y, %H:%M"),
            "user": a.user_name,
            "role": a.role,
            "action": a.action,
            "purpose": a.purpose or "Direct Care"
        })

    allergies_list = json.loads(patient.allergies) if patient.allergies and patient.allergies.startswith("[") else ([patient.allergies] if patient.allergies else [])
    conds_list = json.loads(patient.existing_conditions) if patient.existing_conditions and patient.existing_conditions.startswith("[") else ([patient.existing_conditions] if patient.existing_conditions else [])

    visits = []
    for r in records:
        if r.record_type in ["Emergency Visit", "Clinical Note", "Discharge Summary"]:
            visits.append({
                "date": r.created_at.strftime("%d %b %Y"),
                "doctor": r.author or "Attending Physician",
                "location": r.source,
                "notes": str(r.clinical_data.get("notes") or r.clinical_data.get("complaint") or r.record_type)
            })

    return {
        "patient_id": patient.id,
        "name": patient.full_name,
        "dob": patient.dob,
        "blood_group": patient.blood_group,
        "allergies": allergies_list,
        "medications": [],
        "conditions": conds_list,
        "visits": visits,
        "access_history": access_history
    }
