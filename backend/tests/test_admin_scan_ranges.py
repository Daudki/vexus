from app.config.settings import get_settings
from app.users.models import Role, RoleName, User
from app.core.security import hash_password


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


def test_admin_can_manage_scan_ranges(client, db_session):
    token = _create_and_login(client, db_session, "admin_scan", RoleName.ADMIN)
    settings = get_settings()
    original_ranges = list(settings.AUTHORIZED_SCAN_RANGES or [])
    settings.AUTHORIZED_SCAN_RANGES = []

    try:
        resp = client.get("/api/v1/admin/settings/scan-ranges", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        assert resp.json()["ranges"] == []

        update = client.put(
            "/api/v1/admin/settings/scan-ranges",
            headers={"Authorization": f"Bearer {token}"},
            json={"ranges": ["10.0.0.0/8", "192.168.1.0/24"]},
        )
        assert update.status_code == 200
        assert update.json()["ranges"] == ["10.0.0.0/8", "192.168.1.0/24"]
        assert get_settings().AUTHORIZED_SCAN_RANGES == ["10.0.0.0/8", "192.168.1.0/24"]
    finally:
        settings.AUTHORIZED_SCAN_RANGES = original_ranges


def test_non_admin_cannot_manage_scan_ranges(client, db_session):
    token = _create_and_login(client, db_session, "viewer_scan", RoleName.VIEWER)

    resp = client.put(
        "/api/v1/admin/settings/scan-ranges",
        headers={"Authorization": f"Bearer {token}"},
        json={"ranges": ["10.0.0.0/8"]},
    )
    assert resp.status_code == 403
