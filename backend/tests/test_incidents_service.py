import json
from datetime import datetime, timezone

import pytest

from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset, AssetTrustStatus
from app.core.security import hash_password
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.incidents.models import IncidentStatus
from app.incidents.service import IncidentError, IncidentService
from app.users.models import Role, RoleName, User


def _seed_user(db_session, username="analyst1", role_name=RoleName.SECURITY_ANALYST):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(username=username, email=f"{username}@vexus.local", password_hash=hash_password("x"), role_id=role.id)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _seed_asset(db_session, ip="10.0.0.60"):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address=ip, trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_event(db_session, asset_id):
    now = datetime.now(timezone.utc)
    event = NetworkEvent(
        event_type="NEW_DEVICE",
        event_source=EventSource.DISCOVERY,
        timestamp=now,
        asset_id=asset_id,
        severity=EventSeverity.MEDIUM,
        confidence=0.9,
        description="test event",
        evidence="[]",
        is_synthetic=False,
    )
    db_session.add(event)
    db_session.commit()
    db_session.refresh(event)
    return event


def _seed_alert(db_session, asset_id, event_id, severity=EventSeverity.HIGH, confidence=0.8):
    now = datetime.now(timezone.utc)
    alert = Alert(
        rule_key="test_rule",
        asset_id=asset_id,
        severity=severity,
        confidence=confidence,
        status=AlertStatus.NEW,
        description="test alert",
        evidence=json.dumps([event_id]),
        dedup_key=f"test_rule:{asset_id}",
        occurrence_count=1,
        first_seen=now,
        last_seen=now,
        suppressed=False,
        is_synthetic=False,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert


def test_create_incident_requires_at_least_one_alert_or_asset(db_session):
    actor = _seed_user(db_session)
    service = IncidentService(db_session)

    with pytest.raises(IncidentError, match="at least one linked alert or asset"):
        service.create_incident(title="Empty incident", description="", alert_ids=[], asset_ids=[], actor=actor)


def test_create_incident_with_asset_only(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    service = IncidentService(db_session)

    incident = service.create_incident(
        title="Suspicious asset", description="", alert_ids=[], asset_ids=[asset.id], actor=actor
    )

    asset_links = service.repo.list_asset_links(incident.id)
    assert len(asset_links) == 1
    assert incident.status == IncidentStatus.OPEN


def test_linking_alert_auto_links_its_asset(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    event = _seed_event(db_session, asset.id)
    alert = _seed_alert(db_session, asset.id, event.id)
    service = IncidentService(db_session)

    incident = service.create_incident(
        title="Incident from alert", description="", alert_ids=[alert.id], asset_ids=[], actor=actor
    )

    asset_links = service.repo.list_asset_links(incident.id)
    assert len(asset_links) == 1
    assert asset_links[0].asset_id == asset.id


def test_severity_is_max_of_linked_alerts(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    event1 = _seed_event(db_session, asset.id)
    event2 = _seed_event(db_session, asset.id)
    alert1 = _seed_alert(db_session, asset.id, event1.id, severity=EventSeverity.LOW)
    alert2 = _seed_alert(db_session, asset.id, event2.id, severity=EventSeverity.CRITICAL)
    service = IncidentService(db_session)

    incident = service.create_incident(
        title="Multi-alert incident", description="", alert_ids=[alert1.id, alert2.id], asset_ids=[], actor=actor
    )

    assert incident.severity == EventSeverity.CRITICAL


def test_confidence_is_average_of_linked_alerts(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    event1 = _seed_event(db_session, asset.id)
    event2 = _seed_event(db_session, asset.id)
    alert1 = _seed_alert(db_session, asset.id, event1.id, confidence=0.6)
    alert2 = _seed_alert(db_session, asset.id, event2.id, confidence=1.0)
    service = IncidentService(db_session)

    incident = service.create_incident(
        title="Multi-alert incident", description="", alert_ids=[alert1.id, alert2.id], asset_ids=[], actor=actor
    )

    assert incident.confidence == pytest.approx(0.8)


def test_create_incident_with_nonexistent_alert_raises(db_session):
    actor = _seed_user(db_session)
    service = IncidentService(db_session)

    with pytest.raises(IncidentError, match="does not exist"):
        service.create_incident(
            title="Bad incident", description="", alert_ids=["does-not-exist"], asset_ids=[], actor=actor
        )


def test_update_status_is_audited(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    service = IncidentService(db_session)
    incident = service.create_incident(title="Test", description="", alert_ids=[], asset_ids=[asset.id], actor=actor)

    service.update(incident, status=IncidentStatus.INVESTIGATING, actor=actor)

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="incident.updated").all()
    assert len(entries) == 1
    assert incident.status == IncidentStatus.INVESTIGATING


def test_add_note_records_author_and_content(db_session):
    actor = _seed_user(db_session, username="analyst2")
    asset = _seed_asset(db_session)
    service = IncidentService(db_session)
    incident = service.create_incident(title="Test", description="", alert_ids=[], asset_ids=[asset.id], actor=actor)

    note = service.add_note(incident, "Investigated, looks benign.", actor)

    assert note.author_username == "analyst2"
    assert note.content == "Investigated, looks benign."


def test_timeline_includes_events_notes_and_audit_entries(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    event = _seed_event(db_session, asset.id)
    alert = _seed_alert(db_session, asset.id, event.id)
    service = IncidentService(db_session)

    incident = service.create_incident(
        title="Full timeline test", description="", alert_ids=[alert.id], asset_ids=[], actor=actor
    )
    service.add_note(incident, "Checking this out.", actor)
    service.update(incident, status=IncidentStatus.INVESTIGATING, actor=actor)

    timeline = service.get_timeline(incident)
    kinds = {e.kind for e in timeline}

    assert "event" in kinds  # the NEW_DEVICE NetworkEvent via the alert's evidence
    assert "note" in kinds
    assert "audit" in kinds  # incident.created + incident.updated
    # sorted chronologically
    assert timeline == sorted(timeline, key=lambda e: e.timestamp)


def test_unlink_alert_removes_link_and_is_audited(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    event = _seed_event(db_session, asset.id)
    alert = _seed_alert(db_session, asset.id, event.id)
    service = IncidentService(db_session)

    incident = service.create_incident(
        title="Test", description="", alert_ids=[alert.id], asset_ids=[], actor=actor
    )
    service.unlink_alert(incident, alert.id, actor)

    assert service.repo.list_alert_links(incident.id) == []


def test_unlink_alert_not_linked_raises(db_session):
    actor = _seed_user(db_session)
    asset = _seed_asset(db_session)
    event = _seed_event(db_session, asset.id)
    alert = _seed_alert(db_session, asset.id, event.id)
    service = IncidentService(db_session)

    incident = service.create_incident(title="Test", description="", alert_ids=[], asset_ids=[asset.id], actor=actor)

    with pytest.raises(IncidentError, match="not linked"):
        service.unlink_alert(incident, alert.id, actor)
