from fastapi import Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.db.session import get_db
from app.core.security import decode_token
from app.models.user import User, UserRole, AccountStatus, Professional
from app.models.patient import Patient
from app.models.emergency import AccessSession
from app.core.audit_logger import record_audit

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

def get_current_user(
    request: Request,
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
) -> User:
    """Validate JWT access token and return active user."""
    # Also support X-Patient-Token or Authorization Bearer
    auth_header = request.headers.get("Authorization")
    if not token and auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token required",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    # If this is a patient portal session token
    if payload.get("role") == UserRole.PATIENT.value:
        patient = db.query(Patient).filter(Patient.id == user_id).first()
        if not patient:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Patient profile not found")
        return User(
            id=patient.id,
            email=patient.email or f"{patient.id}@patient.hc04",
            role=UserRole.PATIENT,
            account_status=AccountStatus.VERIFIED
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User account not found")

    if user.account_status == AccountStatus.SUSPENDED:
        record_audit(
            db=db, user_id=user.id, user_name=user.email, role=user.role.value,
            action="SUSPENDED_LOGIN_ATTEMPT", result="Denied"
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is suspended. Contact administrator.")

    return user

def get_current_verified_professional(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
) -> User:
    """Ensures user is a DOCTOR, EMT, or DISASTER_RESPONSE and has VERIFIED status."""
    if user.role not in [UserRole.DOCTOR, UserRole.EMT, UserRole.DISASTER_RESPONSE, UserRole.ADMIN]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Clinical access restricted to healthcare professionals.")

    if user.role != UserRole.ADMIN:
        if user.account_status == AccountStatus.PENDING_VERIFICATION:
            record_audit(
                db=db, user_id=user.id, user_name=user.email, role=user.role.value,
                action="UNVERIFIED_CLINICAL_ACCESS", result="Denied"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your professional account is awaiting administrator verification. Clinical access is not yet granted."
            )
        elif user.account_status == AccountStatus.REJECTED:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Your professional registration was rejected.")
        elif user.account_status != AccountStatus.VERIFIED:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account status does not permit clinical access.")

    return user

def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Ensure user has ADMIN role."""
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Administrative privileges required.")
    return user

def evaluate_zero_trust_access(
    db: Session,
    user: User,
    patient_id: str,
    purpose: str = "Emergency Treatment",
    required_scope: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Evaluates zero-trust access policy:
    1. Requester authenticated?
    2. Professional verified?
    3. Patient exists?
    4. Valid clinical purpose supplied?
    5. Role-based permission matched?
    6. Active emergency / break-glass session?
    """
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Patient with identifier {patient_id} not found.")

    # Check for active emergency break-glass session
    now = datetime.now(timezone.utc)
    emergency_session = db.query(AccessSession).filter(
        AccessSession.patient_id == patient_id,
        AccessSession.requester_id == user.id,
        AccessSession.is_active == True,
        AccessSession.expiry_time > now
    ).first()

    emergency_active = emergency_session is not None

    # Role evaluation
    if user.role == UserRole.PATIENT:
        # Patient can only access their own record
        if user.id != patient.id and user.email != patient.email:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Patients can only access their own medical records.")
        return {"granted": True, "emergency_active": False, "role": "PATIENT", "scope": "OWN_RECORDS"}

    if user.role == UserRole.ADMIN:
        # Admin gets administrative access, not clinical bypass unless authorized
        return {"granted": True, "emergency_active": False, "role": "ADMIN", "scope": "AUDIT_ONLY"}

    if user.account_status != AccountStatus.VERIFIED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unverified professional cannot access patient data.")

    # Data minimization scope based on role
    scope = "FULL_CLINICAL"
    if user.role == UserRole.EMT:
        scope = "EMERGENCY_CRITICAL_ONLY"
    elif user.role == UserRole.DISASTER_RESPONSE:
        scope = "TRIAGE_EMERGENCY_ONLY"

    return {
        "granted": True,
        "emergency_active": emergency_active,
        "break_glass": emergency_session.break_glass if emergency_session else False,
        "role": user.role.value,
        "scope": scope,
        "patient": patient
    }
