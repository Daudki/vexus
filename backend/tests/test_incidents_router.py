import json
from datetime import datetime, timezone

from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset, AssetTrustStatus
from app.core.security import hash_password
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.users.models import Role, RoleName, User


def _create_and_login(client, db_session, username, role_name, password="Password123!"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(username=username, email=f"{username}@vexus.local", password_hash=hash_password(password), role_id=role.id)
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def _seed_asset(db_session, ip="10.0.0.70"):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address=ip, trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_alert_with_event(db_session, asset_id):
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

    alert = Alert(
        rule_key="test_rule",
        asset_id=asset_id,
        severity=EventSeverity.HIGH,
        confidence=0.8,
        status=AlertStatus.NEW,
        description="test alert",
        evidence=json.dumps([event.id]),
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


def test_viewer_can_read_but_not_create_incidents(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    list_resp = client.get("/api/v1/incidents", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200

    create_resp = client.post(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test", "asset_ids": [asset.id]},
    )
    assert create_resp.status_code == 403


def test_create_incident_with_no_evidence_returns_400(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post(
        "/api/v1/incidents", headers={"Authorization": f"Bearer {token}"}, json={"title": "Empty"}
    )
    assert resp.status_code == 400


def test_full_incident_workflow(client, db_session):
    alert = _seed_alert_with_event(db_session, _seed_asset(db_session).id)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    create_resp = client.post(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Suspicious device", "description": "Investigating", "alert_ids": [alert.id]},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["severity"] == "high"
    assert len(body["asset_ids"]) == 1
    incident_id = body["id"]

    note_resp = client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        headers={"Authorization": f"Bearer {token}"},
        json={"content": "Confirmed device is a new employee laptop."},
    )
    assert note_resp.status_code == 201

    status_resp = client.patch(
        f"/api/v1/incidents/{incident_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "resolved", "resolution": "Verified benign, employee onboarding."},
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "resolved"

    timeline_resp = client.get(
        f"/api/v1/incidents/{incident_id}/timeline", headers={"Authorization": f"Bearer {token}"}
    )
    assert timeline_resp.status_code == 200
    kinds = {e["kind"] for e in timeline_resp.json()}
    assert "event" in kinds
    assert "note" in kinds
    assert "audit" in kinds


def test_viewer_cannot_add_note(client, db_session):
    asset = _seed_asset(db_session)
    analyst_token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    create_resp = client.post(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {analyst_token}"},
        json={"title": "Test", "asset_ids": [asset.id]},
    )
    incident_id = create_resp.json()["id"]

    viewer_token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post(
        f"/api/v1/incidents/{incident_id}/notes",
        headers={"Authorization": f"Bearer {viewer_token}"},
        json={"content": "trying to add a note"},
    )
    assert resp.status_code == 403


def test_link_and_unlink_additional_asset(client, db_session):
    asset1 = _seed_asset(db_session, ip="10.0.0.71")
    asset2 = _seed_asset(db_session, ip="10.0.0.72")
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    create_resp = client.post(
        "/api/v1/incidents",
        headers={"Authorization": f"Bearer {token}"},
        json={"title": "Test", "asset_ids": [asset1.id]},
    )
    incident_id = create_resp.json()["id"]

    link_resp = client.post(
        f"/api/v1/incidents/{incident_id}/assets",
        headers={"Authorization": f"Bearer {token}"},
        json={"asset_id": asset2.id},
    )
    assert link_resp.status_code == 200
    assert len(link_resp.json()["asset_ids"]) == 2


def test_get_nonexistent_incident_returns_404(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/incidents/does-not-exist", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_filter_incidents_by_status(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    client.post(
        "/api/v1/incidents", headers={"Authorization": f"Bearer {token}"}, json={"title": "Test", "asset_ids": [asset.id]}
    )

    resp = client.get("/api/v1/incidents?status_filter=open", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 1

    resp2 = client.get("/api/v1/incidents?status_filter=closed", headers={"Authorization": f"Bearer {token}"})
    assert resp2.json() == []
