from pydantic import BaseModel
from typing import Optional, Any, Dict
from datetime import datetime

class AuditLogItem(BaseModel):
    id: str
    time: str
    timestamp: datetime
    user: str
    role: str
    action: str
    patient: str
    result: str
    purpose: Optional[str] = None
    emergency_status: str

    class Config:
        from_attributes = True
