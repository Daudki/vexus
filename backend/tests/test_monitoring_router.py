from datetime import datetime, timezone

from app.assets.models import Asset, AssetStatus, AssetTrustStatus
from app.core.security import hash_password
from app.main import app
from app.monitoring.collectors import MonitoringResult, SimulatedCollector
from app.monitoring.router import get_monitoring_collector
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


def _seed_asset(db_session, ip_address, status=AssetStatus.ONLINE):
    now = datetime.now(timezone.utc)
    asset = Asset(
        ip_address=ip_address,
        status=status,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_viewer_cannot_trigger_poll(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post("/api/v1/monitoring/poll", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_overview_before_any_poll_reports_data_quality_warning(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/monitoring/overview", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data_quality_warnings"]) == 1
    assert "has not completed a poll cycle" in body["data_quality_warnings"][0]


def test_successful_poll_updates_overview_and_clears_warning(client, db_session):
    asset = _seed_asset(db_session, "10.0.0.30", status=AssetStatus.ONLINE)
    app.dependency_overrides[get_monitoring_collector] = lambda: SimulatedCollector(
        {"10.0.0.30": MonitoringResult(available=True, latency_ms=15.0, packet_loss_pct=0.0)}
    )

    try:
        token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)
        poll_resp = client.post("/api/v1/monitoring/poll", headers={"Authorization": f"Bearer {token}"})
        assert poll_resp.status_code == 200
        assert poll_resp.json()["assets_checked"] == 1

        overview_resp = client.get("/api/v1/monitoring/overview", headers={"Authorization": f"Bearer {token}"})
        body = overview_resp.json()
        assert body["online"] == 1
        assert body["offline"] == 0
        assert body["average_latency_ms"] == 15.0
        assert body["data_quality_warnings"] == []

        metrics_resp = client.get(
            f"/api/v1/monitoring/assets/{asset.id}/metrics", headers={"Authorization": f"Bearer {token}"}
        )
        assert metrics_resp.status_code == 200
        assert len(metrics_resp.json()) == 3  # availability, latency, packet_loss
    finally:
        app.dependency_overrides.pop(get_monitoring_collector, None)


def test_poll_marking_asset_offline_reflects_in_overview(client, db_session):
    _seed_asset(db_session, "10.0.0.31", status=AssetStatus.ONLINE)
    app.dependency_overrides[get_monitoring_collector] = lambda: SimulatedCollector({})  # unreachable

    try:
        token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)
        client.post("/api/v1/monitoring/poll", headers={"Authorization": f"Bearer {token}"})

        overview_resp = client.get("/api/v1/monitoring/overview", headers={"Authorization": f"Bearer {token}"})
        assert overview_resp.json()["offline"] == 1
    finally:
        app.dependency_overrides.pop(get_monitoring_collector, None)


def test_metrics_for_nonexistent_asset_returns_404(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/monitoring/assets/does-not-exist/metrics", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
