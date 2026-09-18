from app.core.security import hash_password
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


def test_any_authenticated_user_can_view_status(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/simulation/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["active"] is False


def test_only_admin_can_run_scenario(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post("/api/v1/simulation/run", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_admin_can_run_and_reset_scenario(client, db_session):
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)

    run_resp = client.post("/api/v1/simulation/run", headers={"Authorization": f"Bearer {token}"})
    assert run_resp.status_code == 200
    assert run_resp.json()["assets_created"] == 2

    status_resp = client.get("/api/v1/simulation/status", headers={"Authorization": f"Bearer {token}"})
    assert status_resp.json()["active"] is True

    reset_resp = client.post("/api/v1/simulation/reset", headers={"Authorization": f"Bearer {token}"})
    assert reset_resp.status_code == 200
    assert reset_resp.json()["assets_deleted"] == 2

    status_resp = client.get("/api/v1/simulation/status", headers={"Authorization": f"Bearer {token}"})
    assert status_resp.json()["active"] is False


def test_simulated_assets_excluded_from_normal_asset_list(client, db_session):
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    client.post("/api/v1/simulation/run", headers={"Authorization": f"Bearer {token}"})

    resp = client.get("/api/v1/assets", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get(
        "/api/v1/assets", params={"include_synthetic": "true"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert len(resp.json()) == 2


def test_simulated_alerts_excluded_from_normal_alert_list(client, db_session):
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    client.post("/api/v1/simulation/run", headers={"Authorization": f"Bearer {token}"})

    resp = client.get("/api/v1/alerts", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.get(
        "/api/v1/alerts", params={"include_synthetic": "true"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert len(resp.json()) >= 1
