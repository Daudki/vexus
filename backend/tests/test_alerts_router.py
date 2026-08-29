from datetime import datetime, timezone

from app.alerts.models import Alert, AlertStatus
from app.core.security import hash_password
from app.events.models import EventSeverity
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


def _seed_alert(db_session):
    now = datetime.now(timezone.utc)
    alert = Alert(
        rule_key="new_device_detection",
        asset_id=None,
        severity=EventSeverity.MEDIUM,
        confidence=0.9,
        status=AlertStatus.NEW,
        description="test alert",
        evidence="[]",
        dedup_key="new_device_detection:test-asset",
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


def test_list_alerts_requires_authentication(client):
    resp = client.get("/api/v1/alerts")
    assert resp.status_code == 401


def test_viewer_can_list_but_not_update_alerts(client, db_session):
    alert = _seed_alert(db_session)
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    list_resp = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = client.patch(
        f"/api/v1/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "acknowledged"},
    )
    assert update_resp.status_code == 403


def test_analyst_can_update_alert_status_and_it_is_audited(client, db_session):
    alert = _seed_alert(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    resp = client.patch(
        f"/api/v1/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"status": "investigating"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "investigating"

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="alert.update").all()
    assert len(entries) == 1


def test_alert_can_be_assigned_to_a_user(client, db_session):
    alert = _seed_alert(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    # Assigning an alert to a real user, since the API validates that
    # `assigned_to` refers to an existing user (a plain string ID with
    # no matching user is correctly rejected with 400 -- see
    # test_assigning_alert_to_unknown_user_returns_400 below).
    target_role = db_session.query(Role).filter_by(name=RoleName.SECURITY_ANALYST).first()
    target = User(
        username="assignee1",
        email="assignee1@vexus.local",
        password_hash=hash_password("Password123!"),
        role_id=target_role.id,
    )
    db_session.add(target)
    db_session.commit()

    resp = client.patch(
        f"/api/v1/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"assigned_to": target.id},
    )
    assert resp.status_code == 200
    assert resp.json()["assigned_to"] == target.id


def test_assigning_alert_to_unknown_user_returns_400(client, db_session):
    alert = _seed_alert(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    resp = client.patch(
        f"/api/v1/alerts/{alert.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"assigned_to": "some-user-id"},
    )
    assert resp.status_code == 400


def test_filter_alerts_by_status(client, db_session):
    _seed_alert(db_session)
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    resp = client.get("/api/v1/alerts?status_filter=new", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1

    resp2 = client.get("/api/v1/alerts?status_filter=resolved", headers={"Authorization": f"Bearer {token}"})
    assert resp2.json() == []


def test_get_nonexistent_alert_returns_404(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/alerts/does-not-exist", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
