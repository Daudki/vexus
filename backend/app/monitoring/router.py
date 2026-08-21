from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetStatus
from app.core.deps import require_any_role, require_role
from app.database.session import get_db
from app.health.models import WorkerHeartbeat
from app.monitoring.collectors import MonitoringCollector, PingCollector
from app.monitoring.models import MetricType, MonitoringSample
from app.monitoring.schemas import MonitoringSampleRead, NetworkHealthOverview, PollSummaryRead
from app.monitoring.service import MonitoringService
from app.users.models import RoleName, User

router = APIRouter(prefix="/api/v1/monitoring", tags=["monitoring"])

STALE_HEARTBEAT_MINUTES = 15


def get_monitoring_collector() -> MonitoringCollector:
    """Default collector for the running deployment. Overridden in tests
    to inject a SimulatedCollector instead of requiring real ICMP access."""
    return PingCollector()


@router.post("/poll", response_model=PollSummaryRead)
def trigger_poll(
    db: Session = Depends(get_db),
    collector: MonitoringCollector = Depends(get_monitoring_collector),
    _: User = Depends(require_role(RoleName.ADMIN, RoleName.NETWORK_ADMINISTRATOR)),
) -> PollSummaryRead:
    service = MonitoringService(db, collector)
    try:
        summary = service.poll_all()
    except Exception as exc:  # noqa: BLE001 — surface the real failure, never hide it (Rule 4)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Monitoring poll failed: {exc}")
    return summary


@router.get("/assets/{asset_id}/metrics", response_model=list[MonitoringSampleRead])
def get_asset_metrics(
    asset_id: str,
    metric_type: MetricType | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> list[MonitoringSampleRead]:
    if db.get(Asset, asset_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")

    query = select(MonitoringSample).where(MonitoringSample.asset_id == asset_id)
    if metric_type is not None:
        query = query.where(MonitoringSample.metric_type == metric_type)
    query = query.order_by(desc(MonitoringSample.timestamp)).limit(min(limit, 1000))

    return list(db.scalars(query))


@router.get("/overview", response_model=NetworkHealthOverview)
def get_overview(
    db: Session = Depends(get_db),
    _: User = Depends(require_any_role),
) -> NetworkHealthOverview:
    assets = db.query(Asset).all()
    online = sum(1 for a in assets if a.status == AssetStatus.ONLINE)
    offline = sum(1 for a in assets if a.status == AssetStatus.OFFLINE)
    unknown = sum(1 for a in assets if a.status == AssetStatus.UNKNOWN)

    recent_latency = list(
        db.scalars(
            select(MonitoringSample)
            .where(MonitoringSample.metric_type == MetricType.LATENCY_MS)
            .order_by(desc(MonitoringSample.timestamp))
            .limit(200)
        )
    )
    avg_latency = sum(s.value for s in recent_latency) / len(recent_latency) if recent_latency else None

    warnings: list[str] = []
    hb = db.query(WorkerHeartbeat).filter_by(worker_name="monitoring").first()
    if hb is None or hb.last_success_at is None:
        warnings.append(
            "Monitoring has not completed a poll cycle yet. Network health data is incomplete."
        )
    else:
        age_minutes = (datetime.now(timezone.utc) - hb.last_success_at.replace(tzinfo=timezone.utc)).total_seconds() / 60
        if age_minutes > STALE_HEARTBEAT_MINUTES:
            warnings.append(
                f"Monitoring has been unavailable for {int(age_minutes)} minutes. "
                "Asset status and risk calculations may be incomplete."
            )

    return NetworkHealthOverview(
        online=online,
        offline=offline,
        unknown=unknown,
        average_latency_ms=avg_latency,
        data_quality_warnings=warnings,
    )
