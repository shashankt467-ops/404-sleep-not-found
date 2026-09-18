from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Dict, Any

from app.db.session import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.zero_trust import get_current_user
from app.core.audit_logger import record_audit
from app.models.user import User, Professional, Organization, UserRole, AccountStatus
from app.schemas.auth import (
    DoctorRegisterRequest, EMTRegisterRequest, DisasterResponseRegisterRequest,
    LoginRequest, TokenResponse, RefreshTokenRequest
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.post("/doctor/register", status_code=status.HTTP_201_CREATED)
def register_doctor(req: DoctorRegisterRequest, db: Session = Depends(get_db)):
    """Register a new Doctor account. Status set to PENDING_VERIFICATION."""
    # Check if email already registered
    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    # Check if registration number already registered
    existing_reg = db.query(Professional).filter(Professional.reg_number == req.reg_number.strip()).first()
    if existing_reg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Medical registration number already in system.")

    # Find or create organization
    org = db.query(Organization).filter(Organization.name.ilike(req.hospital_name.strip())).first()
    if not org:
        org = Organization(name=req.hospital_name.strip(), org_type="Hospital")
        db.add(org)
        db.commit()
        db.refresh(org)

    new_user = User(
        email=req.email.lower(),
        phone=req.phone,
        password_hash=hash_password(req.password),
        role=UserRole.DOCTOR,
        account_status=AccountStatus.PENDING_VERIFICATION
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    prof = Professional(
        user_id=new_user.id,
        full_name=req.full_name.strip(),
        dob=req.dob,
        reg_number=req.reg_number.strip(),
        licensing_authority=req.licensing_authority.strip(),
        organization_id=org.id,
        department=req.department.strip(),
        professional_email=req.email.lower(),
        phone=req.phone,
        id_proof=req.id_proof or "Govt_Doctor_ID_Submitted.pdf",
        credentials_file=req.credentials_file or "Medical_Council_License.pdf",
        verification_status=AccountStatus.PENDING_VERIFICATION
    )
    db.add(prof)
    db.commit()

    record_audit(
        db=db, user_id=new_user.id, user_name=req.full_name, role="DOCTOR",
        action="PROFESSIONAL_REGISTERED", purpose="Account Creation",
        details={"reg_number": req.reg_number, "hospital": req.hospital_name}
    )

    return {
        "message": "Doctor registration submitted successfully.",
        "user_id": new_user.id,
        "account_status": AccountStatus.PENDING_VERIFICATION.value,
        "status_message": "Your professional account is awaiting administrator verification. You will be able to access clinical functionality once verified."
    }

@router.post("/emt/register", status_code=status.HTTP_201_CREATED)
def register_emt(req: EMTRegisterRequest, db: Session = Depends(get_db)):
    """Register an EMT account. Status set to PENDING_VERIFICATION."""
    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    org = db.query(Organization).filter(Organization.name.ilike(req.organization.strip())).first()
    if not org:
        org = Organization(name=req.organization.strip(), org_type="Emergency Medical Service")
        db.add(org)
        db.commit()
        db.refresh(org)

    new_user = User(
        email=req.email.lower(),
        phone=req.phone,
        password_hash=hash_password(req.password),
        role=UserRole.EMT,
        account_status=AccountStatus.PENDING_VERIFICATION
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    prof = Professional(
        user_id=new_user.id,
        full_name=req.full_name.strip(),
        reg_number=req.emt_id.strip(),
        licensing_authority="National Emergency Medical Authority",
        organization_id=org.id,
        department=req.emergency_service.strip(),
        professional_email=req.email.lower(),
        phone=req.phone,
        credentials_file=req.credentials_file or "EMT_Paramedic_Cert.pdf",
        verification_status=AccountStatus.PENDING_VERIFICATION
    )
    db.add(prof)
    db.commit()

    record_audit(
        db=db, user_id=new_user.id, user_name=req.full_name, role="EMT",
        action="PROFESSIONAL_REGISTERED", purpose="Account Creation",
        details={"emt_id": req.emt_id, "organization": req.organization}
    )

    return {
        "message": "EMT registration submitted successfully.",
        "user_id": new_user.id,
        "account_status": AccountStatus.PENDING_VERIFICATION.value,
        "status_message": "Your EMT account is awaiting administrator verification."
    }

@router.post("/disaster/register", status_code=status.HTTP_201_CREATED)
def register_disaster_response(req: DisasterResponseRegisterRequest, db: Session = Depends(get_db)):
    """Register a Disaster Response account."""
    existing_user = db.query(User).filter(User.email == req.email.lower()).first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already registered.")

    org = db.query(Organization).filter(Organization.name.ilike(req.organization.strip())).first()
    if not org:
        org = Organization(name=req.organization.strip(), org_type="Disaster Response Authority")
        db.add(org)
        db.commit()
        db.refresh(org)

    new_user = User(
        email=req.email.lower(),
        phone=req.phone,
        password_hash=hash_password(req.password),
        role=UserRole.DISASTER_RESPONSE,
        account_status=AccountStatus.PENDING_VERIFICATION
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    prof = Professional(
        user_id=new_user.id,
        full_name=req.full_name.strip(),
        reg_number=req.org_id.strip(),
        licensing_authority="National Disaster Management Authority",
        organization_id=org.id,
        department=req.role_title.strip(),
        professional_email=req.email.lower(),
        phone=req.phone,
        verification_status=AccountStatus.PENDING_VERIFICATION
    )
    db.add(prof)
    db.commit()

    record_audit(
        db=db, user_id=new_user.id, user_name=req.full_name, role="DISASTER_RESPONSE",
        action="PROFESSIONAL_REGISTERED", purpose="Account Creation"
    )

    return {
        "message": "Disaster Response account registered successfully.",
        "user_id": new_user.id,
        "account_status": AccountStatus.PENDING_VERIFICATION.value,
        "status_message": "Account awaiting administrative authorization."
    }

@router.post("/login", response_model=TokenResponse)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """
    Authenticate user (Doctor, EMT, Disaster Response, Admin).
    Checks credentials and returns access and refresh tokens along with verification status.
    """
    user = db.query(User).filter(User.email == req.email.lower().strip()).first()
    
    # Also support login by professional registration number
    if not user:
        prof = db.query(Professional).filter(Professional.reg_number == req.email.strip()).first()
        if prof and prof.user:
            user = prof.user

    if not user or not verify_password(req.password, user.password_hash):
        record_audit(
            db=db, user_id=None, user_name=req.email, role="UNKNOWN",
            action="LOGIN_FAILED", result="Denied", ip_address=request.client.host if request.client else None
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email/registration number or password."
        )

    if user.account_status == AccountStatus.SUSPENDED:
        record_audit(
            db=db, user_id=user.id, user_name=user.email, role=user.role.value,
            action="SUSPENDED_LOGIN_ATTEMPT", result="Denied", ip_address=request.client.host if request.client else None
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been suspended by an administrator. Access denied."
        )

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.commit()

    # Determine display name and organization
    user_name = user.email
    hospital_name = "HC-04 Network"
    if user.professional_profile:
        user_name = user.professional_profile.full_name
        if user.professional_profile.organization:
            hospital_name = user.professional_profile.organization.name

    permissions = ["READ_BASIC"]
    if user.account_status == AccountStatus.VERIFIED:
        if user.role == UserRole.DOCTOR:
            permissions = ["REGISTER_PATIENT", "ADD_RECORD", "QUERY_EHR", "EMERGENCY_SUMMARY", "RESOLVE_CONFLICT", "BREAK_GLASS"]
        elif user.role == UserRole.EMT:
            permissions = ["QUERY_EHR", "EMERGENCY_SUMMARY", "VIEW_CRITICAL_ALERTS"]
        elif user.role == UserRole.DISASTER_RESPONSE:
            permissions = ["QUERY_EHR", "EMERGENCY_SUMMARY", "TRIAGE_ACCESS"]
        elif user.role == UserRole.ADMIN:
            permissions = ["VERIFY_PROFESSIONALS", "MANAGE_ORGS", "VIEW_AUDIT_TRAIL", "SYSTEM_HEALTH"]

    token_data = {
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "status": user.account_status.value
    }
    access_token = create_access_token(token_data)
    refresh_token = create_refresh_token(token_data)

    record_audit(
        db=db, user_id=user.id, user_name=user_name, role=user.role.value,
        action="LOGIN", purpose="Console Access", result="Allowed",
        ip_address=request.client.host if request.client else None
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user.id,
        user_name=user_name,
        email=user.email,
        role=user.role.value,
        account_status=user.account_status.value,
        hospital=hospital_name,
        permissions=permissions
    )

@router.post("/doctor/login", response_model=TokenResponse)
def doctor_login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    """Dedicated doctor login endpoint."""
    return login(req, request, db)

@router.post("/refresh")
def refresh_token(req: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Rotate access token using a valid refresh token."""
    payload = decode_token(req.refresh_token, is_refresh=True)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token.")

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user or user.account_status == AccountStatus.SUSPENDED:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account inactive or suspended.")

    new_access_token = create_access_token({
        "sub": user.id,
        "email": user.email,
        "role": user.role.value,
        "status": user.account_status.value
    })
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Audit user logout."""
    record_audit(
        db=db, user_id=user.id, user_name=user.email, role=user.role.value,
        action="LOGOUT", result="Allowed"
    )
    return {"message": "Logged out successfully."}

@router.get("/me")
def get_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user information."""
    if user.role == UserRole.PATIENT:
        patient = db.query(Patient).filter(Patient.id == user.id).first()
        name = patient.full_name if patient else user.email
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role.value,
            "status": user.account_status.value,
            "name": name,
            "reg_number": None,
            "hospital": "HC-04 Patient Portal",
            "department": "Patient Access"
        }
    prof = user.professional_profile
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role.value,
        "status": user.account_status.value,
        "name": prof.full_name if prof else user.email,
        "reg_number": prof.reg_number if prof else None,
        "hospital": prof.organization.name if (prof and prof.organization) else "HC-04 Network",
        "department": prof.department if prof else None
    }
