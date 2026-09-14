from datetime import datetime, timedelta, timezone

from app.assets.models import Asset, AssetStatus, AssetTrustStatus
from app.health.models import WorkerHeartbeat
from app.monitoring.models import MetricType, MonitoringSample
from app.sense.service import SenseService


def _seed_asset(db_session, ip_address):
    now = datetime.now(timezone.utc)
    asset = Asset(
        ip_address=ip_address,
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_latency_samples(db_session, asset_id, values):
    now = datetime.now(timezone.utc)
    for i, value in enumerate(values):
        db_session.add(
            MonitoringSample(
                asset_id=asset_id,
                metric_type=MetricType.LATENCY_MS,
                value=value,
                timestamp=now - timedelta(minutes=(len(values) - i)),
            )
        )
    db_session.commit()


def test_evaluate_all_assets_covers_every_asset_with_samples(db_session):
    quiet_asset = _seed_asset(db_session, "10.0.0.60")
    spiking_asset = _seed_asset(db_session, "10.0.0.61")

    _seed_latency_samples(db_session, quiet_asset.id, [10, 11, 10, 9, 10, 11, 10, 10])
    _seed_latency_samples(db_session, spiking_asset.id, [10, 11, 10, 9, 10, 11, 10, 500])

    events = SenseService(db_session).evaluate_all_assets()

    asset_ids_with_events = {event.asset_id for event in events}
    assert spiking_asset.id in asset_ids_with_events
    assert quiet_asset.id not in asset_ids_with_events


def test_evaluate_all_assets_with_no_samples_returns_empty_and_writes_heartbeat(db_session):
    events = SenseService(db_session).evaluate_all_assets()
    assert events == []

    hb = db_session.query(WorkerHeartbeat).filter_by(worker_name="sense").first()
    assert hb is not None
    assert hb.status == "ok"
    assert hb.last_success_at is not None
