from datetime import datetime, timezone

from app.assets.models import Asset, AssetStatus, AssetTrustStatus
from app.core.security import hash_password
from app.users.models import Role, RoleName, User


def _create_and_login(client, db_session, username, role_name, password="Password123!"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(username=username, email=f"{username}@vexus.local", password_hash=hash_password(password), role_id=role.id)
    db_session.add(user)
    db_session.commit()
    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def _seed_asset(db_session):
    now = datetime.now(timezone.utc)
    asset = Asset(
        hostname="host-1", ip_address="10.0.0.5", status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_only_admin_can_enroll(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post(f"/api/v1/device-management/devices/{asset.id}/enroll", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_can_enroll_and_gets_token(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    resp = client.post(f"/api/v1/device-management/devices/{asset.id}/enroll", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["enrollment_token"]) > 20
    assert body["device"]["status"] == "pending_enrollment"


def test_viewer_can_list_devices(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/device-management/devices", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_queue_reboot_without_confirm_returns_403(client, db_session):
    asset = _seed_asset(db_session)
    admin_token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    enroll_resp = client.post(
        f"/api/v1/device-management/devices/{asset.id}/enroll", headers={"Authorization": f"Bearer {admin_token}"}
    )
    enrollment_token = enroll_resp.json()["enrollment_token"]
    agent_resp = client.post("/api/v1/agent/enroll", json={"enrollment_token": enrollment_token})
    device_id = agent_resp.json()["device_id"]

    resp = client.post(
        f"/api/v1/device-management/devices/{device_id}/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action_type": "reboot", "confirm": False},
    )
    assert resp.status_code == 403


def test_full_enroll_task_completion_flow(client, db_session):
    asset = _seed_asset(db_session)
    admin_token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)

    enroll_resp = client.post(
        f"/api/v1/device-management/devices/{asset.id}/enroll", headers={"Authorization": f"Bearer {admin_token}"}
    )
    enrollment_token = enroll_resp.json()["enrollment_token"]

    agent_resp = client.post(
        "/api/v1/agent/enroll",
        json={"enrollment_token": enrollment_token, "agent_version": "1.0", "reported_os": "Linux"},
    )
    assert agent_resp.status_code == 200
    agent_token = agent_resp.json()["agent_token"]
    device_id = agent_resp.json()["device_id"]

    queue_resp = client.post(
        f"/api/v1/device-management/devices/{device_id}/tasks",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"action_type": "status_check", "confirm": False},
    )
    assert queue_resp.status_code == 200
    task_id = queue_resp.json()["id"]

    poll_resp = client.get("/api/v1/agent/tasks/next", headers={"Authorization": f"Bearer {agent_token}"})
    assert poll_resp.status_code == 200
    assert poll_resp.json()["id"] == task_id

    result_resp = client.post(
        f"/api/v1/agent/tasks/{task_id}/result",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={"success": True, "result": "all good"},
    )
    assert result_resp.status_code == 200
    assert result_resp.json()["status"] == "completed"


def test_agent_endpoint_requires_agent_token_not_user_jwt(client, db_session):
    user_token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    resp = client.get("/api/v1/agent/tasks/next", headers={"Authorization": f"Bearer {user_token}"})
    assert resp.status_code == 401


def test_revoked_agent_token_stops_authenticating(client, db_session):
    asset = _seed_asset(db_session)
    admin_token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    enroll_resp = client.post(
        f"/api/v1/device-management/devices/{asset.id}/enroll", headers={"Authorization": f"Bearer {admin_token}"}
    )
    agent_resp = client.post(
        "/api/v1/agent/enroll", json={"enrollment_token": enroll_resp.json()["enrollment_token"]}
    )
    agent_token = agent_resp.json()["agent_token"]
    device_id = agent_resp.json()["device_id"]

    revoke_resp = client.post(
        f"/api/v1/device-management/devices/{device_id}/revoke", headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert revoke_resp.status_code == 200

    poll_resp = client.get("/api/v1/agent/tasks/next", headers={"Authorization": f"Bearer {agent_token}"})
    assert poll_resp.status_code == 401
