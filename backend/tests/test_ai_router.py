import json
from datetime import datetime, timezone

from app.ai.router import get_ai_provider
from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset, AssetTrustStatus
from app.core.security import hash_password
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.main import app
from app.users.models import Role, RoleName, User

from tests.test_ai_service import FakeProvider


def _create_and_login(client, db_session, username, role_name, password="Password123!"):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(username=username, email=f"{username}@vexus.local", password_hash=hash_password(password), role_id=role.id)
    db_session.add(user)
    db_session.commit()

    resp = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    return resp.json()["access_token"]


def _seed_alert_with_event(db_session):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address="10.0.0.90", trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()

    event = NetworkEvent(
        event_type="NEW_DEVICE", event_source=EventSource.DISCOVERY, timestamp=now, asset_id=asset.id,
        severity=EventSeverity.MEDIUM, confidence=0.9, description="test event", evidence="[]", is_synthetic=False,
    )
    db_session.add(event)
    db_session.commit()

    alert = Alert(
        rule_key="new_device_detection", asset_id=asset.id, severity=EventSeverity.MEDIUM, confidence=0.9,
        status=AlertStatus.NEW, description="test alert", evidence=json.dumps([event.id]),
        dedup_key=f"new_device_detection:{asset.id}", occurrence_count=1, first_seen=now, last_seen=now,
        suppressed=False, is_synthetic=False,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    return alert


def test_status_reflects_default_unconfigured_settings(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/ai/status", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["provider"] == "none"
    assert resp.json()["configured"] is False


def test_viewer_cannot_request_explanation(client, db_session):
    alert = _seed_alert_with_event(db_session)
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    resp = client.post(f"/api/v1/ai/alerts/{alert.id}/explain", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_viewer_can_list_past_queries(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/ai/queries", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_analyst_can_explain_alert_with_injected_fake_provider(client, db_session):
    alert = _seed_alert_with_event(db_session)
    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider()

    try:
        token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
        resp = client.post(f"/api/v1/ai/alerts/{alert.id}/explain", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["observed_facts"] == ["fact"]
        assert body["confidence"] == 0.75

        list_resp = client.get("/api/v1/ai/queries", headers={"Authorization": f"Bearer {token}"})
        assert len(list_resp.json()) == 1
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_explain_nonexistent_alert_returns_404(client, db_session):
    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider()
    try:
        token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
        resp = client.post("/api/v1/ai/alerts/does-not-exist/explain", headers={"Authorization": f"Bearer {token}"})
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_ask_endpoint_with_asset_context(client, db_session):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address="10.0.0.91", trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()

    app.dependency_overrides[get_ai_provider] = lambda: FakeProvider()
    try:
        token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
        resp = client.post(
            "/api/v1/ai/ask",
            headers={"Authorization": f"Bearer {token}"},
            json={"context_type": "asset", "context_id": asset.id, "question": "Is this risky?"},
        )
        assert resp.status_code == 200
        assert resp.json()["question"] == "Is this risky?"
    finally:
        app.dependency_overrides.pop(get_ai_provider, None)


def test_default_provider_is_null_when_unconfigured(client, db_session):
    """Without dependency override, the real get_ai_provider() is used —
    with AI_PROVIDER=none (test default), this must resolve to NullProvider
    and succeed with a 'not configured' response, never error out."""
    alert = _seed_alert_with_event(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    resp = client.post(f"/api/v1/ai/alerts/{alert.id}/explain", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["confidence"] == 0.0
    assert "not configured" in resp.json()["recommendations"][0]
