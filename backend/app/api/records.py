from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import List, Dict, Any

from app.db.session import get_db
from app.core.zero_trust import get_current_verified_professional, evaluate_zero_trust_access
from app.core.audit_logger import record_audit
from app.models.user import User, UserRole
from app.models.patient import Patient
from app.models.medical_record import MedicalRecord, RecordVersion, RecordType
from app.schemas.record import (
    MedicalRecordCreateRequest, MedicalRecordUpdateRequest,
    MedicalRecordResponse, RecordVersionResponse
)

router = APIRouter(tags=["Medical Records"])

@router.post("/patients/{id}/records", response_model=MedicalRecordResponse, status_code=status.HTTP_201_CREATED)
def create_medical_record(
    id: str,
    req: MedicalRecordCreateRequest,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Authorized Doctor adds a medical record for a patient.
    Record types: Diagnosis, Allergy, Medication, Procedure, Surgery,
    Laboratory Result, Vital Signs, Emergency Visit, Discharge Summary, Clinical Note.
    Creates initial version in RecordVersion.
    """
    patient = db.query(Patient).filter(Patient.id == id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    evaluate_zero_trust_access(db, current_user, patient.id, purpose="Add Medical Record")

    prof = current_user.professional_profile
    author_name = prof.full_name if prof else current_user.email
    source_name = req.source or (prof.organization.name if (prof and prof.organization) else "HC-04 Medical Center")
    org_id = prof.organization_id if prof else None

    record = MedicalRecord(
        patient_id=patient.id,
        provider_id=current_user.id,
        organization_id=org_id,
        record_type=req.record_type,
        clinical_data=req.clinical_data,
        source=source_name,
        author=author_name,
        is_active=True
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    # Create initial version
    version = RecordVersion(
        record_id=record.id,
        version_num=1,
        previous_value=None,
        new_value=req.clinical_data,
        changed_by=author_name,
        reason="Initial clinical entry"
    )
    db.add(version)
    db.commit()
    db.refresh(record)

    record_audit(
        db=db, user_id=current_user.id, user_name=author_name,
        role=current_user.role.value, action="MEDICAL_RECORD_CREATED",
        patient_id=patient.id, purpose="Clinical Documentation",
        details={"record_id": record.id, "record_type": record.record_type}
    )

    return record

@router.get("/patients/{id}/records", response_model=List[MedicalRecordResponse])
def get_patient_records(
    id: str,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """Retrieve all active medical records and their versions for a patient."""
    patient = db.query(Patient).filter(Patient.id == id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found.")

    evaluate_zero_trust_access(db, current_user, patient.id, purpose="View Medical Records")

    records = db.query(MedicalRecord).filter(
        MedicalRecord.patient_id == patient.id,
        MedicalRecord.is_active == True
    ).order_by(MedicalRecord.created_at.desc()).all()

    record_audit(
        db=db, user_id=current_user.id,
        user_name=current_user.professional_profile.full_name if current_user.professional_profile else current_user.email,
        role=current_user.role.value, action="MEDICAL_RECORDS_VIEWED",
        patient_id=patient.id, purpose="Clinical Care",
        details={"records_retrieved": len(records)}
    )

    return records

@router.put("/records/{id}", response_model=MedicalRecordResponse)
def update_medical_record(
    id: str,
    req: MedicalRecordUpdateRequest,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Update a medical record with mandatory versioning history.
    Never silently overwrites clinical information.
    """
    record = db.query(MedicalRecord).filter(MedicalRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found.")

    evaluate_zero_trust_access(db, current_user, record.patient_id, purpose="Update Medical Record")

    prof = current_user.professional_profile
    changer_name = prof.full_name if prof else current_user.email

    previous_val = record.clinical_data
    latest_version = db.query(RecordVersion).filter(RecordVersion.record_id == record.id).order_by(RecordVersion.version_num.desc()).first()
    new_version_num = (latest_version.version_num + 1) if latest_version else 2

    # Save new version entry
    version_entry = RecordVersion(
        record_id=record.id,
        version_num=new_version_num,
        previous_value=previous_val,
        new_value=req.clinical_data,
        changed_by=changer_name,
        reason=req.reason
    )
    db.add(version_entry)

    # Update current record
    record.clinical_data = req.clinical_data
    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)

    record_audit(
        db=db, user_id=current_user.id, user_name=changer_name,
        role=current_user.role.value, action="MEDICAL_RECORD_UPDATED",
        patient_id=record.patient_id, purpose="Clinical Modification",
        details={"record_id": record.id, "version": new_version_num, "reason": req.reason}
    )

    return record

@router.get("/records/{id}/history", response_model=List[RecordVersionResponse])
def get_record_version_history(
    id: str,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """View full audit and version history for a specific clinical record."""
    record = db.query(MedicalRecord).filter(MedicalRecord.id == id).first()
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medical record not found.")

    versions = db.query(RecordVersion).filter(
        RecordVersion.record_id == record.id
    ).order_by(RecordVersion.version_num.desc()).all()

    return versions
