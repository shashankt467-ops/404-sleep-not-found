from sqlalchemy.orm import Session
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.models.audit import AuditLog

def record_audit(
    db: Session,
    user_id: Optional[str],
    user_name: str,
    role: str,
    action: str,
    patient_id: Optional[str] = None,
    purpose: Optional[str] = "Direct Clinical Care",
    result: str = "Allowed",
    emergency_status: str = "Normal",
    ip_address: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None
) -> AuditLog:
    """Record an immutable-style audit log entry into the database."""
    log_entry = AuditLog(
        timestamp=datetime.now(timezone.utc),
        user_id=user_id,
        user_name=user_name,
        role=role,
        patient_id=patient_id,
        action=action,
        purpose=purpose,
        result=result,
        emergency_status=emergency_status,
        ip_address=ip_address,
        details=details
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)
    return log_entry
