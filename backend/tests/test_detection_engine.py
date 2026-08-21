import json
from datetime import datetime, timedelta, timezone

from app.alerts.models import Alert
from app.assets.models import Asset, AssetTrustStatus
from app.detection.service import DetectionEngine
from app.events.models import EventSeverity, EventSource, NetworkEvent


def _seed_asset(db_session):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address="10.0.0.9", trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_event(db_session, asset_id, event_type, confidence=1.0, severity=EventSeverity.MEDIUM, timestamp=None):
    event = NetworkEvent(
        event_type=event_type,
        event_source=EventSource.DISCOVERY,
        timestamp=timestamp or datetime.now(timezone.utc),
        asset_id=asset_id,
        severity=severity,
        confidence=confidence,
        description=f"test {event_type}",
        evidence="[]",
        is_synthetic=False,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def test_new_device_event_produces_an_alert(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "NEW_DEVICE")

    summary = DetectionEngine(db_session).run()

    assert summary.events_evaluated == 1
    assert summary.findings_produced == 1
    assert summary.alerts_created == 1

    alerts = db_session.query(Alert).all()
    assert len(alerts) == 1
    assert alerts[0].rule_key == "new_device_detection"
    assert alerts[0].asset_id == asset.id


def test_event_is_marked_processed_after_run(db_session):
    asset = _seed_asset(db_session)
    event = _seed_event(db_session, asset.id, "NEW_DEVICE")

    DetectionEngine(db_session).run()

    db_session.refresh(event)
    assert event.processed_by_detection is True


def test_rerunning_does_not_reprocess_already_processed_events(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "NEW_DEVICE")

    DetectionEngine(db_session).run()
    second_summary = DetectionEngine(db_session).run()

    assert second_summary.events_evaluated == 0
    assert second_summary.alerts_created == 0


def test_low_confidence_event_does_not_produce_a_finding(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "NEW_DEVICE", confidence=0.1)  # below default 0.7 threshold

    summary = DetectionEngine(db_session).run()

    assert summary.findings_produced == 0
    assert db_session.query(Alert).count() == 0


def test_mac_change_rule_overrides_severity_to_high(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "MAC_CHANGED", severity=EventSeverity.MEDIUM)

    DetectionEngine(db_session).run()

    alert = db_session.query(Alert).filter_by(rule_key="mac_change_detection").first()
    assert alert is not None
    assert alert.severity == EventSeverity.HIGH  # engine judgment overrides the raw event's MEDIUM


def test_repeated_events_within_suppression_window_merge_into_one_alert(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "AVAILABILITY_ANOMALY")

    engine = DetectionEngine(db_session)
    engine.run()

    # a second, independent AVAILABILITY_ANOMALY event for the same asset shortly after
    _seed_event(db_session, asset.id, "AVAILABILITY_ANOMALY")
    engine.run()

    alerts = db_session.query(Alert).filter_by(rule_key="availability_anomaly_detection").all()
    assert len(alerts) == 1
    assert alerts[0].occurrence_count == 2

    evidence = json.loads(alerts[0].evidence)
    assert len(evidence) == 2


def test_alert_starts_suppressed_when_alert_threshold_not_yet_met(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "NEW_DEVICE")

    engine = DetectionEngine(db_session)
    config = engine.get_or_create_config("new_device_detection")
    from app.detection.repository import DetectionRuleConfigRepository

    DetectionRuleConfigRepository(db_session).update(config, alert_threshold=3)

    engine.run()

    alert = db_session.query(Alert).first()
    assert alert.suppressed is True  # occurrence_count=1 < alert_threshold=3


def test_disabled_rule_produces_no_alert(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "NEW_DEVICE")

    engine = DetectionEngine(db_session)
    config = engine.get_or_create_config("new_device_detection")
    from app.detection.repository import DetectionRuleConfigRepository

    DetectionRuleConfigRepository(db_session).update(config, enabled=False)

    summary = engine.run()

    assert summary.findings_produced == 0
    assert db_session.query(Alert).count() == 0


def test_closed_alert_does_not_get_reused_by_dedup(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "NEW_DEVICE")

    engine = DetectionEngine(db_session)
    engine.run()

    alert = db_session.query(Alert).first()
    from app.alerts.models import AlertStatus

    alert.status = AlertStatus.RESOLVED
    db_session.commit()

    _seed_event(db_session, asset.id, "NEW_DEVICE")
    engine.run()

    all_alerts = db_session.query(Alert).filter_by(rule_key="new_device_detection").all()
    assert len(all_alerts) == 2  # a fresh alert, not a reuse of the resolved one


def test_unregistered_event_type_is_ignored(db_session):
    asset = _seed_asset(db_session)
    _seed_event(db_session, asset.id, "SOME_UNKNOWN_EVENT_TYPE")

    summary = DetectionEngine(db_session).run()

    assert summary.events_evaluated == 0  # not fetched at all — not a registered rule's event_type
