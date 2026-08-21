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


def test_admin_can_list_users(client, db_session):
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_viewer_cannot_list_users(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/users", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_security_analyst_cannot_create_users(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "new1", "email": "new1@vexus.local", "password": "Password123!", "role": "viewer"},
    )
    assert resp.status_code == 403


def test_admin_can_create_and_role_change_is_audited(client, db_session):
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    create_resp = client.post(
        "/api/v1/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"username": "new1", "email": "new1@vexus.local", "password": "Password123!", "role": "viewer"},
    )
    assert create_resp.status_code == 201
    user_id = create_resp.json()["id"]

    role_resp = client.patch(
        f"/api/v1/users/{user_id}/role",
        headers={"Authorization": f"Bearer {token}"},
        json={"role": "security_analyst"},
    )
    assert role_resp.status_code == 200
    assert role_resp.json()["role"] == "security_analyst"

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="user.role_change").all()
    assert len(entries) == 1
    assert "security_analyst" in entries[0].detail


def test_any_authenticated_user_can_read_own_profile(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "viewer1"
