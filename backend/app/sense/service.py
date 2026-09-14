from __future__ import annotations

from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

from sqlalchemy import and_, desc
from sqlalchemy.orm import Session

from app.assets.models import Asset
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.health.models import WorkerHeartbeat
from app.monitoring.models import MetricType, MonitoringSample
from app.sense.models import BehavioralBaseline

DEFAULT_BASELINE_WINDOW_MINUTES = 24 * 60
DEFAULT_MIN_SAMPLES = 5


class SenseService:
    def __init__(self, db: Session):
        self.db = db

    def compute_baseline(
        self,
        asset_id: str,
        metric_type: MetricType,
        *,
        window_minutes: int = DEFAULT_BASELINE_WINDOW_MINUTES,
        min_samples: int = DEFAULT_MIN_SAMPLES,
    ) -> BehavioralBaseline:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=window_minutes)

        samples = (
            self.db.query(MonitoringSample)
            .filter(
                and_(
                    MonitoringSample.asset_id == asset_id,
                    MonitoringSample.metric_type == metric_type,
                    MonitoringSample.timestamp >= cutoff,
                )
            )
            .order_by(MonitoringSample.timestamp.asc())
            .all()
        )

        values = [sample.value for sample in samples]
        if values:
            avg = mean(values)
            stddev = pstdev(values) if len(values) > 1 else 0.0
            min_value = min(values)
            max_value = max(values)
            sample_count = len(values)
            is_usable = sample_count >= min_samples
            notes = "" if is_usable else "Insufficient historical samples for a reliable baseline."
        else:
            avg = 0.0
            stddev = 0.0
            min_value = 0.0
            max_value = 0.0
            sample_count = 0
            is_usable = False
            notes = "No sample history available for this metric."

        existing = (
            self.db.query(BehavioralBaseline)
            .filter_by(asset_id=asset_id, metric_type=metric_type)
            .first()
        )
        if existing is None:
            baseline = BehavioralBaseline(
                asset_id=asset_id,
                metric_type=metric_type,
                sample_count=sample_count,
                average_value=avg,
                stddev_value=stddev,
                min_value=min_value,
                max_value=max_value,
                window_start=cutoff,
                window_end=now,
                is_usable=is_usable,
                notes=notes,
            )
            self.db.add(baseline)
        else:
            existing.sample_count = sample_count
            existing.average_value = avg
            existing.stddev_value = stddev
            existing.min_value = min_value
            existing.max_value = max_value
            existing.window_start = cutoff
            existing.window_end = now
            existing.is_usable = is_usable
            existing.notes = notes
            baseline = existing

        self.db.commit()
        return baseline

    def evaluate_asset(self, asset_id: str) -> list[NetworkEvent]:
        asset = self.db.get(Asset, asset_id)
        if asset is None:
            return []

        metric_types = (
            self.db.query(MonitoringSample.metric_type)
            .filter(MonitoringSample.asset_id == asset_id)
            .distinct()
            .all()
        )

        events: list[NetworkEvent] = []
        for (metric_type,) in metric_types:
            latest_sample = (
                self.db.query(MonitoringSample)
                .filter_by(asset_id=asset_id, metric_type=metric_type)
                .order_by(desc(MonitoringSample.timestamp))
                .first()
            )
            if latest_sample is None:
                continue

            prior_samples = (
                self.db.query(MonitoringSample)
                .filter(
                    MonitoringSample.asset_id == asset_id,
                    MonitoringSample.metric_type == metric_type,
                    MonitoringSample.timestamp < latest_sample.timestamp,
                )
                .order_by(MonitoringSample.timestamp.asc())
                .all()
            )
            if not prior_samples:
                continue

            historical_values = [sample.value for sample in prior_samples]
            if len(historical_values) < DEFAULT_MIN_SAMPLES:
                continue

            avg = mean(historical_values)
            stddev = pstdev(historical_values) if len(historical_values) > 1 else 0.0

            value = latest_sample.value

            if stddev == 0:
                threshold = max(avg * 1.5, 10.0)
                if value > threshold:
                    anomaly = True
                    score = max(0.0, min(1.0, (value / max(avg, 1.0)) - 1.0))
                else:
                    anomaly = False
                    score = 0.0
            else:
                z_score = abs(value - avg) / max(stddev, 1.0)
                anomaly = z_score >= 3.0
                score = min(1.0, z_score / 6.0)

            if not anomaly:
                continue

            severity = EventSeverity.HIGH if score >= 0.7 else EventSeverity.MEDIUM
            confidence = max(0.6, min(0.99, score + 0.4))

            event = NetworkEvent(
                event_type="BEHAVIORAL_ANOMALY",
                event_source=EventSource.MONITORING,
                timestamp=latest_sample.timestamp,
                asset_id=asset.id,
                severity=severity,
                confidence=confidence,
                description=(
                    f"{metric_type.value} deviated from the asset baseline: "
                    f"observed {value:.2f} vs historical baseline {avg:.2f} ± {stddev:.2f}."
                ),
                evidence=(
                    '{"metric_type": "' + metric_type.value + '", "value": ' + str(value) +
                    ', "baseline_average": ' + str(avg) + ', "baseline_stddev": ' + str(stddev) + '}'
                ),
                is_synthetic=False,
                processed_by_detection=False,
            )
            self.db.add(event)
            events.append(event)

        self.db.commit()
        return events

    def evaluate_all_assets(self) -> list[NetworkEvent]:
        """Run evaluate_asset() across every asset with monitoring history.

        Thin wrapper only — all anomaly-detection logic stays in
        evaluate_asset() so there is exactly one implementation of that
        behavior (see VEXUS v2 Development Rules, "do not introduce a
        second implementation of the same subsystem"). Used by both the
        manual trigger endpoint and the background scheduler.
        """
        asset_ids = [
            row[0]
            for row in self.db.query(MonitoringSample.asset_id).distinct().all()
        ]

        events: list[NetworkEvent] = []
        for asset_id in asset_ids:
            events.extend(self.evaluate_asset(asset_id))

        self._update_heartbeat(status="ok", detail=f"{len(asset_ids)} assets evaluated, {len(events)} anomalies")
        return events

    def _update_heartbeat(self, *, status: str, detail: str) -> None:
        hb = self.db.query(WorkerHeartbeat).filter_by(worker_name="sense").first()
        now = datetime.now(timezone.utc)
        if hb is None:
            hb = WorkerHeartbeat(worker_name="sense")
            self.db.add(hb)
        hb.last_success_at = now if status == "ok" else hb.last_success_at
        hb.status = status
        hb.detail = detail
        self.db.commit()
