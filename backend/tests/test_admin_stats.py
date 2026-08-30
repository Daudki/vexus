from datetime import datetime, timezone

from app.assets.models import Asset, AssetStatus
from app.core.security import hash_password
from app.events.models import EventSeverity
from app.incidents.models import Incident, IncidentStatus
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


def test_admin_stats_counts_use_real_status_values(client, db_session):
    """Regression test: a previous version filtered Asset.status == "active"
    and Incident.status.in_(["new", ...]) -- values that never occur in
    either enum (real values are "online" and "open") -- so both counts
    were always silently zero. This confirms the fix."""
    token = _create_and_login(client, db_session, "admin_stats", RoleName.ADMIN)

    now = datetime.now(timezone.utc)
    db_session.add(
        Asset(
            ip_address="10.0.0.5",
            status=AssetStatus.ONLINE,
            first_seen=now,
            last_seen=now,
        )
    )
    db_session.add(
        Incident(
            title="Test incident",
            severity=EventSeverity.HIGH,
            confidence=0.8,
            status=IncidentStatus.OPEN,
        )
    )
    db_session.commit()

    resp = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_assets"] == 1
    assert body["active_assets"] == 1
    assert body["total_incidents"] == 1
    assert body["open_incidents"] == 1


def test_non_admin_cannot_view_stats(client, db_session):
    token = _create_and_login(client, db_session, "viewer_stats", RoleName.VIEWER)
    resp = client.get("/api/v1/admin/stats", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_users_and_roles_crud_endpoints_are_removed(client, db_session):
    """User/role management lives at /api/v1/users, not /api/v1/admin/*
    (see app/users/router.py). These paths previously existed as a
    duplicate, untested reimplementation that crashed on first real use
    (wrong AuditLog/Role column names, an incompatible 3-value RoleName).
    They've been removed rather than fixed in place, since the correct
    versions already exist and are tested elsewhere."""
    token = _create_and_login(client, db_session, "admin_removed", RoleName.ADMIN)
    headers = {"Authorization": f"Bearer {token}"}

    assert client.get("/api/v1/admin/users", headers=headers).status_code == 404
    assert client.get("/api/v1/admin/roles", headers=headers).status_code == 404
    assert client.get("/api/v1/admin/audit", headers=headers).status_code == 404
