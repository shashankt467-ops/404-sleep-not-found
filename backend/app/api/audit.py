from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.db.session import get_db
from app.core.zero_trust import get_current_user
from app.models.audit import AuditLog
from app.schemas.audit import AuditLogItem

router = APIRouter(prefix="/audit-logs", tags=["Audit Trail"])

@router.get("", response_model=List[AuditLogItem])
def get_audit_logs(
    patient_id: Optional[str] = None,
    action: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve immutable audit events with optional patient or action filters."""
    query = db.query(AuditLog)
    if patient_id:
        query = query.filter(AuditLog.patient_id == patient_id.strip().upper())
    if action:
        query = query.filter(AuditLog.action.ilike(f"%{action.strip()}%"))

    logs = query.order_by(AuditLog.timestamp.desc()).limit(limit).all()

    results = []
    for l in logs:
        results.append(AuditLogItem(
            id=l.id,
            time=l.timestamp.strftime("%H:%M"),
            timestamp=l.timestamp,
            user=l.user_name,
            role=l.role,
            action=l.action,
            patient=l.patient_id or "—",
            result=l.result,
            purpose=l.purpose,
            emergency_status=l.emergency_status
        ))
    return results
