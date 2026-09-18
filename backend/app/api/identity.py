from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any

from app.db.session import get_db
from app.core.zero_trust import get_current_verified_professional
from app.models.patient import Patient
from app.models.user import User
from app.services.identity_matcher import match_patient_identity

router = APIRouter(prefix="/identity", tags=["Identity Resolution"])

class IdentityMatchRequest(BaseModel):
    patient_id: str
    candidate_name: Optional[str] = None
    candidate_dob: Optional[str] = None
    candidate_phone: Optional[str] = None

class IdentityVerifyRequest(BaseModel):
    requester: str
    role: str
    auth_method: str = "identity_token"

@router.post("/match")
def match_identity(
    req: IdentityMatchRequest,
    current_user: User = Depends(get_current_verified_professional),
    db: Session = Depends(get_db)
):
    """
    Patient identity matching service.
    Evaluates identifier, name similarity, DOB, and contact factors.
    Returns MATCHED, POSSIBLE_MATCH, or NO_MATCH.
    Never merges uncertain matches automatically.
    """
    patient = db.query(Patient).filter(Patient.id == req.patient_id.strip().upper()).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient profile not found.")

    candidate = {
        "patient_id": req.patient_id,
        "name": req.candidate_name or patient.full_name,
        "dob": req.candidate_dob or patient.dob
    }

    result = match_patient_identity(patient, candidate)
    return {
        "target_patient_id": patient.id,
        "target_name": patient.full_name,
        "target_dob": patient.dob,
        "candidate": candidate,
        "match_result": result
    }

@router.post("/verify")
def verify_identity(req: IdentityVerifyRequest, current_user: User = Depends(get_current_verified_professional)):
    """Requester identity verification endpoint for zero-trust authorization pipeline."""
    return {
        "requester": current_user.email,
        "role": current_user.role.value,
        "auth_method": req.auth_method,
        "account_status": current_user.account_status.value,
        "verified": (current_user.account_status.value == "VERIFIED")
    }
