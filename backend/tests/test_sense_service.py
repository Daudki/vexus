from datetime import datetime, timedelta, timezone

from app.assets.models import Asset, AssetStatus, AssetTrustStatus
from app.events.models import NetworkEvent
from app.monitoring.models import MetricType, MonitoringSample
from app.sense.models import BehavioralBaseline
from app.sense.service import SenseService


def _seed_asset(db_session, ip_address, status=AssetStatus.ONLINE, last_seen=None):
    now = last_seen or datetime.now(timezone.utc)
    asset = Asset(
        ip_address=ip_address,
        status=status,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_sense_service_creates_baseline_and_detects_latency_spike(db_session):
    asset = _seed_asset(db_session, "10.0.0.50")
    now = datetime.now(timezone.utc)

    for i in range(8):
        db_session.add(
            MonitoringSample(
                asset_id=asset.id,
                metric_type=MetricType.LATENCY_MS,
                value=22.0 + (i % 3),
                timestamp=now - timedelta(minutes=10 * (8 - i)),
            )
        )

    db_session.commit()

    service = SenseService(db_session)
    baseline = service.compute_baseline(asset.id, MetricType.LATENCY_MS)

    assert isinstance(baseline, BehavioralBaseline)
    assert baseline.sample_count == 8
    assert baseline.average_value > 20

    db_session.add(
        MonitoringSample(
            asset_id=asset.id,
            metric_type=MetricType.LATENCY_MS,
            value=180.0,
            timestamp=now,
        )
    )
    db_session.commit()

    anomalies = service.evaluate_asset(asset.id)
    assert any(event.event_type == "BEHAVIORAL_ANOMALY" for event in anomalies)

    event = next(event for event in anomalies if event.event_type == "BEHAVIORAL_ANOMALY")
    assert event.asset_id == asset.id
    assert event.severity.value in {"medium", "high"}


def test_sense_service_warns_when_baseline_is_underpowered(db_session):
    asset = _seed_asset(db_session, "10.0.0.51")
    now = datetime.now(timezone.utc)

    for i in range(2):
        db_session.add(
            MonitoringSample(
                asset_id=asset.id,
                metric_type=MetricType.PACKET_LOSS_PCT,
                value=1.0,
                timestamp=now - timedelta(minutes=5 * (2 - i)),
            )
        )
    db_session.commit()

    service = SenseService(db_session)
    baseline = service.compute_baseline(asset.id, MetricType.PACKET_LOSS_PCT, min_samples=5)

    assert baseline.sample_count == 2
    assert baseline.is_usable is False
