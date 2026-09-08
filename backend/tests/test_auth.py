from app.core.security import hash_password
from app.users.models import Role, RoleName, User


def _create_user(db_session, username="admin1", role_name=RoleName.ADMIN, password="AdminPass123!"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(
        username=username,
        email=f"{username}@vexus.local",
        password_hash=hash_password(password),
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_with_wrong_password_returns_401(client, db_session):
    _create_user(db_session)
    resp = client.post("/api/v1/auth/login", json={"username": "admin1", "password": "wrong"})
    assert resp.status_code == 401


def test_login_with_unknown_user_returns_401(client, db_session):
    resp = client.post("/api/v1/auth/login", json={"username": "ghost", "password": "whatever"})
    assert resp.status_code == 401


def test_successful_login_returns_token_pair(client, db_session):
    _create_user(db_session)
    resp = client.post("/api/v1/auth/login", json={"username": "admin1", "password": "AdminPass123!"})
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body and "refresh_token" in body


def test_successful_login_accepts_email(client, db_session):
    _create_user(db_session)
    resp = client.post("/api/v1/auth/login", json={"username": "admin1@vexus.local", "password": "AdminPass123!"})
    assert resp.status_code == 200


def test_me_requires_authentication(client):
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user_with_valid_token(client, db_session):
    _create_user(db_session)
    login = client.post("/api/v1/auth/login", json={"username": "admin1", "password": "AdminPass123!"})
    token = login.json()["access_token"]

    resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["username"] == "admin1"


def test_failed_login_is_audited(client, db_session):
    _create_user(db_session)
    client.post("/api/v1/auth/login", json={"username": "admin1", "password": "wrong"})

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="login", success=False).all()
    assert len(entries) == 1
