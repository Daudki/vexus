from datetime import datetime, timezone

from app.assets.models import Asset, AssetTrustStatus
from app.core.security import hash_password
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.users.models import Role, RoleName, User


def _create_and_login(client, db_session, username, role_name, password="Password123!"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(
        username=username,
        email=f"{username}@vexus.local",
        password_hash=hash_password(password),
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def _seed_new_device_event(db_session):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address="10.0.0.9", trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)

    event = NetworkEvent(
        event_type="NEW_DEVICE",
        event_source=EventSource.DISCOVERY,
        timestamp=now,
        asset_id=asset.id,
        severity=EventSeverity.MEDIUM,
        confidence=1.0,
        description="test",
        evidence="[]",
        is_synthetic=False,
    )
    db_session.add(event)
    db_session.commit()
    return asset


def test_viewer_cannot_trigger_detection_run(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post("/api/v1/detection/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_security_analyst_can_trigger_run_and_it_creates_alerts(client, db_session):
    _seed_new_device_event(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    resp = client.post("/api/v1/detection/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["alerts_created"] == 1

    alerts_resp = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {token}"})
    assert alerts_resp.status_code == 200
    assert len(alerts_resp.json()) == 1
    assert alerts_resp.json()[0]["rule_key"] == "new_device_detection"


def test_rule_list_returns_all_registered_rules_with_defaults(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/detection/rules", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    rule_keys = {r["rule_key"] for r in resp.json()}
    assert rule_keys == {
        "new_device_detection",
        "ip_change_detection",
        "mac_change_detection",
        "availability_anomaly_detection",
        "asset_missing_detection",
    }


def test_catalog_shows_implemented_and_not_implemented_rules(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/detection/rules/catalog", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert "new_device_detection" in body["implemented"]
    assert "traffic_volume_anomaly" in body["not_implemented"]


def test_viewer_cannot_update_rule_config(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    client.get("/api/v1/detection/rules", headers={"Authorization": f"Bearer {token}"})  # ensure config exists

    resp = client.patch(
        "/api/v1/detection/rules/new_device_detection",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": False},
    )
    assert resp.status_code == 403


def test_admin_can_disable_a_rule_and_it_is_audited(client, db_session):
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    client.get("/api/v1/detection/rules", headers={"Authorization": f"Bearer {token}"})

    resp = client.patch(
        "/api/v1/detection/rules/new_device_detection",
        headers={"Authorization": f"Bearer {token}"},
        json={"enabled": False},
    )
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="detection.rule_config_updated").all()
    assert len(entries) == 1
