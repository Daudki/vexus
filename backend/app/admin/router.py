"""
Admin-only functionality that isn't already covered elsewhere.

User/role management lives at /api/v1/users (create, role changes,
activate/deactivate, password reset, delete) and the audit trail is
readable at /api/v1/audit-logs — see app/users/router.py and
app/audit/router.py. This module previously duplicated both with an
incompatible, untested reimplementation (a second 3-value RoleName,
wrong AuditLog/Role column names that crashed on first use, no
last-admin-lockout protection). That duplicate surface has been
removed; only the genuinely admin-specific, non-duplicated endpoints
remain: authorized scan ranges and the system stats dashboard.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.admin.schemas import ScanRangesResponse, ScanRangesUpdate, SystemStats
from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset, AssetStatus
from app.audit.service import AuditService
from app.core.deps import require_role
from app.database.session import get_db
from app.incidents.models import Incident, IncidentStatus
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get(
    "/settings/scan-ranges",
    response_model=ScanRangesResponse,
    dependencies=[Depends(require_role(RoleName.ADMIN))],
)
def get_scan_ranges(db: Session = Depends(get_db)) -> ScanRangesResponse:
    """Get the currently authorized discovery scan ranges."""
    from app.config.settings import get_settings

    settings = get_settings()
    return ScanRangesResponse(ranges=list(settings.authorized_scan_ranges_list))


@router.put("/settings/scan-ranges", response_model=ScanRangesResponse)
def update_scan_ranges(
    payload: ScanRangesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(RoleName.ADMIN)),
) -> ScanRangesResponse:
    """Persist the set of CIDR ranges administrators are allowed to scan."""
    from app.config.settings import get_settings

    ranges = [str(entry).strip() for entry in payload.ranges if str(entry).strip()]

    settings = get_settings()
    settings.AUTHORIZED_SCAN_RANGES = ranges
    AuditService(db).record(
        action="admin.update_scan_ranges",
        actor=current_user,
        target_type="system",
        target_id="scan_ranges",
        detail=f"Updated authorized scan ranges: {', '.join(ranges) if ranges else 'none'}",
    )
    return ScanRangesResponse(ranges=ranges)


@router.get(
    "/stats",
    response_model=SystemStats,
    dependencies=[Depends(require_role(RoleName.ADMIN))],
)
def get_system_stats(db: Session = Depends(get_db)) -> SystemStats:
    """Get system statistics (admin only).

    Filters use the real enum values from each module's model
    (AssetStatus.ONLINE = "online", IncidentStatus.OPEN = "open") —
    a previous version filtered on "active"/"new" respectively, values
    that never actually occur in either column, so both counts were
    always silently zero.
    """
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active.is_(True)).count()

    total_assets = db.query(Asset).count()
    active_assets = db.query(Asset).filter(Asset.status == AssetStatus.ONLINE).count()

    total_alerts = db.query(Alert).count()
    new_alerts = db.query(Alert).filter(Alert.status == AlertStatus.NEW).count()

    total_incidents = db.query(Incident).count()
    open_incidents = (
        db.query(Incident)
        .filter(Incident.status.in_([IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]))
        .count()
    )

    return SystemStats(
        total_users=total_users,
        active_users=active_users,
        total_assets=total_assets,
        active_assets=active_assets,
        total_alerts=total_alerts,
        new_alerts=new_alerts,
        total_incidents=total_incidents,
        open_incidents=open_incidents,
        health_status="healthy",
    )
