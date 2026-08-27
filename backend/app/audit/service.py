from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.users.models import User


class AuditService:
    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        action: str,
        actor: Optional[User] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        detail: Optional[str] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
    ) -> AuditLog:
        """Record an audit entry."""
        log = AuditLog(
            action=action,
            user_id=actor.id if actor else None,
            resource_type=target_type,
            resource_id=target_id,
            details={"detail": detail, "success": success} if detail else {"success": success},
            ip_address=ip_address,
            timestamp=datetime.utcnow(),
        )
        self.db.add(log)
        self.db.flush()
        return log