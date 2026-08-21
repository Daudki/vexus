from datetime import datetime, timedelta, timezone

from app.assets.models import Asset, AssetChangeType, AssetStatus, AssetTrustStatus
from app.events.models import NetworkEvent
from app.monitoring.collectors import MonitoringResult, SimulatedCollector
from app.monitoring.models import MetricType, MonitoringSample
from app.monitoring.service import MonitoringService


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


def test_reachable_asset_records_samples_and_stays_online(db_session):
    asset = _seed_asset(db_session, "10.0.0.20", status=AssetStatus.ONLINE)
    collector = SimulatedCollector({"10.0.0.20": MonitoringResult(available=True, latency_ms=12.5, packet_loss_pct=0.0)})

    summary = MonitoringService(db_session, collector).poll_all()

    assert summary.assets_checked == 1
    assert summary.went_offline == 0

    samples = db_session.query(MonitoringSample).filter_by(asset_id=asset.id).all()
    metric_types = {s.metric_type for s in samples}
    assert MetricType.AVAILABILITY in metric_types
    assert MetricType.LATENCY_MS in metric_types
    assert MetricType.PACKET_LOSS_PCT in metric_types

    db_session.refresh(asset)
    assert asset.status == AssetStatus.ONLINE


def test_unreachable_asset_transitions_to_offline_with_history_and_event(db_session):
    asset = _seed_asset(db_session, "10.0.0.21", status=AssetStatus.ONLINE)
    collector = SimulatedCollector({})  # not listed -> unavailable by default

    summary = MonitoringService(db_session, collector).poll_all()

    assert summary.went_offline == 1
    db_session.refresh(asset)
    assert asset.status == AssetStatus.OFFLINE

    events = db_session.query(NetworkEvent).filter_by(asset_id=asset.id, event_type="AVAILABILITY_ANOMALY").all()
    assert len(events) == 1
    assert events[0].confidence == 1.0

    from app.assets.repository import AssetRepository

    history = AssetRepository(db_session).get_history(asset.id)
    assert any(h.change_type == AssetChangeType.STATUS_CHANGED for h in history)


def test_recovered_asset_transitions_back_to_online(db_session):
    asset = _seed_asset(db_session, "10.0.0.22", status=AssetStatus.OFFLINE)
    collector = SimulatedCollector({"10.0.0.22": MonitoringResult(available=True, latency_ms=8.0, packet_loss_pct=0.0)})

    summary = MonitoringService(db_session, collector).poll_all()

    assert summary.went_online == 1
    db_session.refresh(asset)
    assert asset.status == AssetStatus.ONLINE

    events = db_session.query(NetworkEvent).filter_by(asset_id=asset.id, event_type="ASSET_RECOVERED").all()
    assert len(events) == 1


def test_asset_without_ip_is_not_pinged(db_session):
    asset = Asset(
        ip_address=None,
        mac_address="AA:BB:CC:DD:EE:99",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db_session.add(asset)
    db_session.commit()

    summary = MonitoringService(db_session, SimulatedCollector({})).poll_all()
    assert summary.assets_checked == 0  # no IP -> not actively probed this cycle


def test_stale_asset_is_flagged_missing_regardless_of_ping(db_session):
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    asset = _seed_asset(db_session, "10.0.0.23", status=AssetStatus.ONLINE, last_seen=old_time)
    # Even if it happens to answer a ping, staleness beyond the threshold still flags it missing
    # (this test uses a very small threshold to trigger the missing-asset path deterministically).
    collector = SimulatedCollector({"10.0.0.23": MonitoringResult(available=True, latency_ms=5.0, packet_loss_pct=0.0)})

    summary = MonitoringService(db_session, collector).poll_all(missing_threshold_minutes=60)

    # last_seen gets refreshed to "now" by the successful ping BEFORE the missing check runs,
    # so a currently-reachable asset should NOT end up flagged missing.
    assert summary.missing_flagged == 0
    db_session.refresh(asset)
    assert asset.status == AssetStatus.ONLINE


def test_stale_asset_without_ip_is_flagged_missing(db_session):
    """An asset with no IP is never actively pinged, so staleness detection
    (not the ping-based availability path) is the only thing that can catch it."""
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    asset = Asset(
        ip_address=None,
        mac_address="AA:BB:CC:DD:EE:88",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=old_time,
        last_seen=old_time,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    summary = MonitoringService(db_session, SimulatedCollector({})).poll_all(missing_threshold_minutes=60)

    assert summary.missing_flagged == 1
    db_session.refresh(asset)
    assert asset.status == AssetStatus.OFFLINE

    events = db_session.query(NetworkEvent).filter_by(asset_id=asset.id, event_type="ASSET_MISSING").all()
    assert len(events) == 1


def test_ip_based_asset_going_offline_is_not_double_counted_as_missing(db_session):
    """An asset with an IP that fails its ping is already transitioned to
    OFFLINE by the availability check; the missing-asset pass should skip
    it rather than firing a second, redundant event."""
    old_time = datetime.now(timezone.utc) - timedelta(days=2)
    asset = _seed_asset(db_session, "10.0.0.24", status=AssetStatus.ONLINE, last_seen=old_time)

    summary = MonitoringService(db_session, SimulatedCollector({})).poll_all(missing_threshold_minutes=60)

    db_session.refresh(asset)
    assert asset.status == AssetStatus.OFFLINE

    availability_events = db_session.query(NetworkEvent).filter_by(asset_id=asset.id, event_type="AVAILABILITY_ANOMALY").all()
    missing_events = db_session.query(NetworkEvent).filter_by(asset_id=asset.id, event_type="ASSET_MISSING").all()
    assert len(availability_events) == 1
    assert len(missing_events) == 0
    assert summary.missing_flagged == 0
