"""
Audit log viewing (admin-only, read-only).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.audit.models import AuditLog
from app.audit.schemas import AuditLogRead
from app.core.deps import require_role
from app.database.session import get_db
from app.users.models import RoleName

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit"])


@router.get(
    "",
    response_model=list[AuditLogRead],
    dependencies=[Depends(require_role(RoleName.ADMIN))],
)
def list_audit_logs(
    db: Session = Depends(get_db),
    action: Optional[str] = Query(None, description="Filter by exact action, e.g. 'user.delete'"),
    target_type: Optional[str] = Query(None, description="Filter by target type, e.g. 'user'"),
    target_id: Optional[str] = Query(None, description="Filter by target id"),
    actor_username: Optional[str] = Query(None, description="Filter by actor username"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AuditLogRead]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_type:
        query = query.filter(AuditLog.target_type == target_type)
    if target_id:
        query = query.filter(AuditLog.target_id == target_id)
    if actor_username:
        query = query.filter(AuditLog.actor_username == actor_username)

    entries = (
        query.order_by(AuditLog.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [AuditLogRead.model_validate(e) for e in entries]
