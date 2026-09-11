from datetime import datetime, timedelta, timezone

from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset
from app.correlation.service import CorrelationService
from app.events.models import EventSeverity


def _seed_asset(db_session):
    asset = Asset(ip_address="10.0.0.10", first_seen=datetime.now(timezone.utc), last_seen=datetime.now(timezone.utc))
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_alert(db_session, asset_id, seen_at, *, severity=EventSeverity.MEDIUM, confidence=0.8, **kwargs):
    alert = Alert(
        rule_key=f"rule-{seen_at.timestamp()}",
        asset_id=asset_id,
        severity=severity,
        confidence=confidence,
        status=kwargs.get("status", AlertStatus.NEW),
        description="correlation test",
        evidence="[]",
        dedup_key=f"dedup-{seen_at.timestamp()}",
        occurrence_count=1,
        first_seen=seen_at,
        last_seen=seen_at,
        suppressed=kwargs.get("suppressed", False),
        is_synthetic=kwargs.get("is_synthetic", False),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert


def test_correlates_active_alerts_on_same_asset(db_session):
    asset = _seed_asset(db_session)
    base = datetime.now(timezone.utc)
    first = _seed_alert(db_session, asset.id, base, severity=EventSeverity.LOW)
    second = _seed_alert(db_session, asset.id, base + timedelta(minutes=5), severity=EventSeverity.CRITICAL, confidence=1.0)

    candidates = CorrelationService(db_session).find_candidates()

    assert len(candidates) == 1
    assert candidates[0].alert_ids == [first.id, second.id]
    assert candidates[0].severity == EventSeverity.CRITICAL
    assert candidates[0].confidence == 0.9


def test_does_not_correlate_singletons_or_closed_alerts(db_session):
    asset = _seed_asset(db_session)
    base = datetime.now(timezone.utc)
    _seed_alert(db_session, asset.id, base)
    _seed_alert(db_session, asset.id, base + timedelta(minutes=1), status=AlertStatus.RESOLVED)

    assert CorrelationService(db_session).find_candidates() == []


def test_window_and_synthetic_flag_are_respected(db_session):
    asset = _seed_asset(db_session)
    base = datetime.now(timezone.utc)
    _seed_alert(db_session, asset.id, base, is_synthetic=True)
    _seed_alert(db_session, asset.id, base + timedelta(minutes=20))

    assert CorrelationService(db_session).find_candidates(window_seconds=900) == []
    candidates = CorrelationService(db_session).find_candidates(window_seconds=1800)
    assert len(candidates) == 1
    assert candidates[0].is_synthetic is True
