from app.core.security import hash_password
from app.events.models import NetworkEvent
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


def test_security_analyst_can_ingest_events(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post(
        "/api/v1/events/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"events": [{"event_type": "SYSLOG_LOGIN_FAILURE", "event_source": "syslog"}]},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ingested_count"] == 1
    assert body["unmatched_asset_count"] == 0


def test_viewer_cannot_ingest_events(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post(
        "/api/v1/events/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"events": [{"event_type": "SYSLOG_LOGIN_FAILURE", "event_source": "syslog"}]},
    )
    assert resp.status_code == 403


def test_cannot_ingest_events_claiming_discovery_or_monitoring_source(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    for spoofed_source in ("discovery", "monitoring", "simulation"):
        resp = client.post(
            "/api/v1/events/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"events": [{"event_type": "X", "event_source": spoofed_source}]},
        )
        assert resp.status_code == 422, spoofed_source


def test_batch_ingest_is_all_or_nothing(client, db_session):
    """If one event in a batch is invalid (bad asset_id), nothing in the
    batch commits -- no confusing partial ingest."""
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post(
        "/api/v1/events/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "events": [
                {"event_type": "GOOD_EVENT", "event_source": "syslog"},
                {"event_type": "BAD_EVENT", "event_source": "syslog", "asset_id": "does-not-exist"},
            ]
        },
    )
    assert resp.status_code == 400
    assert db_session.query(NetworkEvent).filter_by(event_type="GOOD_EVENT").first() is None


def test_empty_batch_is_rejected(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.post(
        "/api/v1/events/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"events": []},
    )
    assert resp.status_code == 422
