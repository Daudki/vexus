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
        """Record an audit entry.

        `actor` may be None (e.g. a failed login for a username that
        doesn't exist). `target_type`/`target_id`/`detail`/`ip_address`
        are NOT NULL in the schema, so sensible defaults are used when
        the caller doesn't have a specific target (e.g. a login event).
        """
        log = AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else "unknown",
            action=action,
            target_type=target_type or "none",
            target_id=target_id or "",
            detail=detail or "",
            ip_address=ip_address or "",
            success=success,
        )
        self.db.add(log)
        self.db.commit()
        return log
