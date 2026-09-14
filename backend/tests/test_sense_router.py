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


def test_evaluate_all_returns_200_with_empty_list_when_no_anomalies(client, db_session):
    """Unlike the per-asset endpoint (which 404s on no anomalies), the
    bulk endpoint returns 200 + [] -- no anomalies across the fleet is
    the normal case, not an error."""
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post("/api/v1/sense/evaluate-all", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_viewer_cannot_trigger_evaluate_all(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post("/api/v1/sense/evaluate-all", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403
