"""
Audit log schemas.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: str
    actor_user_id: Optional[str] = None
    actor_username: str
    action: str
    target_type: str
    target_id: str
    detail: str
    ip_address: str
    success: bool
    created_at: datetime

    class Config:
        from_attributes = True
