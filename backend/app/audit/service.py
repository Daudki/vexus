from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.users.models import User


class AuditService:
    """The only writer of AuditLog rows. Never exposes update/delete."""

    def __init__(self, db: Session):
        self.db = db

    def record(
        self,
        *,
        action: str,
        actor: User | None = None,
        target_type: str = "",
        target_id: str = "",
        detail: str = "",
        ip_address: str = "",
        success: bool = True,
    ) -> AuditLog:
        entry = AuditLog(
            actor_user_id=actor.id if actor else None,
            actor_username=actor.username if actor else "anonymous",
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=ip_address,
            success=success,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
