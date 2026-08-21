"""
Monitoring application service.

`poll_all` is one cycle of Watch: ping every asset with a known IP,
record metric samples, and detect online<->offline transitions. A
separate, staleness-based pass (`_flag_missing_assets`) catches assets
that haven't been confirmed present in a long time regardless of
whether they were actively pingable this cycle — this is the piece
that was explicitly deferred from Phase 2 (Discover), since it needs
periodic polling rather than a one-off scan.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetChangeType, AssetHistory, AssetStatus
from app.assets.repository import AssetRepository
from app.common.models import DataQualityWarning
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.health.models import WorkerHeartbeat
from app.monitoring.collectors import MonitoringCollector
from app.monitoring.models import MetricType, MonitoringSample

DEFAULT_MISSING_THRESHOLD_MINUTES = 60 * 24  # an asset unseen for a full day is "missing"


@dataclass
class PollSummary:
    assets_checked: int
    went_offline: int
    went_online: int
    missing_flagged: int


class MonitoringService:
    def __init__(self, db: Session, collector: MonitoringCollector):
        self.db = db
        self.collector = collector
        self.repo = AssetRepository(db)

    def poll_all(self, missing_threshold_minutes: int = DEFAULT_MISSING_THRESHOLD_MINUTES) -> PollSummary:
        now = datetime.now(timezone.utc)

        try:
            pingable_assets = [
                a for a in self.db.query(Asset).all() if a.ip_address
            ]

            went_offline = 0
            went_online = 0

            for asset in pingable_assets:
                result = self.collector.check(asset.ip_address)

                self._record_sample(asset.id, MetricType.AVAILABILITY, 1.0 if result.available else 0.0, now)
                if result.latency_ms is not None:
                    self._record_sample(asset.id, MetricType.LATENCY_MS, result.latency_ms, now)
                if result.packet_loss_pct is not None:
                    self._record_sample(asset.id, MetricType.PACKET_LOSS_PCT, result.packet_loss_pct, now)

                new_status = AssetStatus.ONLINE if result.available else AssetStatus.OFFLINE
                if new_status != asset.status:
                    self._transition_status(asset, new_status, now, source="monitoring")
                    if new_status == AssetStatus.OFFLINE:
                        went_offline += 1
                    else:
                        went_online += 1

                if result.available:
                    asset.last_seen = now
                    self.db.commit()

            missing_flagged = self._flag_missing_assets(missing_threshold_minutes, now)

            self._update_heartbeat(status="ok", detail=f"{len(pingable_assets)} assets polled")

            return PollSummary(
                assets_checked=len(pingable_assets),
                went_offline=went_offline,
                went_online=went_online,
                missing_flagged=missing_flagged,
            )

        except Exception as exc:  # noqa: BLE001 — never hide monitoring failures (Rule 4)
            self._update_heartbeat(status="degraded", detail=str(exc))
            self.db.add(
                DataQualityWarning(
                    subject_type="monitoring",
                    subject_id=None,
                    message=f"Monitoring poll cycle failed: {exc}",
                )
            )
            self.db.commit()
            raise

    # --- internal ---

    def _record_sample(self, asset_id: str, metric_type: MetricType, value: float, timestamp: datetime) -> None:
        self.db.add(MonitoringSample(asset_id=asset_id, metric_type=metric_type, value=value, timestamp=timestamp))
        self.db.commit()

    def _transition_status(self, asset: Asset, new_status: AssetStatus, now: datetime, *, source: str) -> None:
        self.db.add(
            AssetHistory(
                asset_id=asset.id,
                change_type=AssetChangeType.STATUS_CHANGED,
                previous_value=asset.status.value,
                new_value=new_status.value,
                source=source,
                changed_at=now,
            )
        )
        previous_status = asset.status
        asset.status = new_status
        self.db.commit()

        if new_status == AssetStatus.OFFLINE:
            event_type, severity, description = (
                "AVAILABILITY_ANOMALY",
                EventSeverity.MEDIUM,
                f"Asset became unreachable (was {previous_status.value}).",
            )
        else:
            event_type, severity, description = (
                "ASSET_RECOVERED",
                EventSeverity.INFORMATIONAL,
                "Asset is reachable again.",
            )

        self.db.add(
            NetworkEvent(
                event_type=event_type,
                event_source=EventSource.MONITORING,
                timestamp=now,
                asset_id=asset.id,
                severity=severity,
                confidence=1.0,  # directly measured via ping, not inferred
                description=description,
                evidence=json.dumps({"previous_status": previous_status.value, "new_status": new_status.value}),
                is_synthetic=False,
            )
        )
        self.db.commit()

    def _flag_missing_assets(self, threshold_minutes: int, now: datetime) -> int:
        threshold = now - timedelta(minutes=threshold_minutes)
        stale_assets = (
            self.db.query(Asset)
            .filter(Asset.last_seen < threshold, Asset.status != AssetStatus.OFFLINE)
            .all()
        )

        for asset in stale_assets:
            self.db.add(
                AssetHistory(
                    asset_id=asset.id,
                    change_type=AssetChangeType.STATUS_CHANGED,
                    previous_value=asset.status.value,
                    new_value=AssetStatus.OFFLINE.value,
                    source="monitoring",
                    changed_at=now,
                )
            )
            asset.status = AssetStatus.OFFLINE
            self.db.commit()

            self.db.add(
                NetworkEvent(
                    event_type="ASSET_MISSING",
                    event_source=EventSource.MONITORING,
                    timestamp=now,
                    asset_id=asset.id,
                    severity=EventSeverity.MEDIUM,
                    confidence=1.0,
                    description=(
                        f"Asset has not been observed since {asset.last_seen.isoformat()}, "
                        f"exceeding the {threshold_minutes}-minute missing-asset threshold."
                    ),
                    evidence=json.dumps({"last_seen": asset.last_seen.isoformat(), "threshold_minutes": threshold_minutes}),
                    is_synthetic=False,
                )
            )
            self.db.commit()

        return len(stale_assets)

    def _update_heartbeat(self, *, status: str, detail: str) -> None:
        hb = self.db.query(WorkerHeartbeat).filter_by(worker_name="monitoring").first()
        now = datetime.now(timezone.utc)
        if hb is None:
            hb = WorkerHeartbeat(worker_name="monitoring")
            self.db.add(hb)
        if status == "ok":
            hb.last_success_at = now
        hb.status = status
        hb.detail = detail
        self.db.commit()
