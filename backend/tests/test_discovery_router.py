from datetime import datetime, timezone
from app.assets.models import Asset, AssetStatus
from app.assets.service import DiscoveredHost
from app.discovery.collectors import SimulatedCollector
from app.discovery.router import get_discovery_collector
from app.main import app
from app.users.models import Role, RoleName, User
from app.auth.router import create_access_token


def _create_and_login(client, db_session, username, role_name, password="Pass123"):
    """Create a user and return auth token directly without password hashing."""
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(
        username=username,
        email=f"{username}@vexus.local",
        password_hash="$2b$12$mockhashmockhashmockhashmockhashmockhashmockhashmockhashmock",
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()

    # Generate token directly instead of via login endpoint to avoid bcrypt issues
    return create_access_token(data={"sub": username})


def test_viewer_cannot_start_scan(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post(
        "/api/v1/discovery/scans",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_ranges": ["10.0.0.0/24"]},
    )
    assert resp.status_code == 403


def test_scan_outside_authorized_range_is_refused(client, db_session, monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')

    token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)
    resp = client.post(
        "/api/v1/discovery/scans",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_ranges": ["192.168.1.0/24"]},
    )
    assert resp.status_code == 400
    assert "not within any authorized" in resp.json()["detail"]

    settings_module.get_settings.cache_clear()


def test_successful_scan_creates_assets_and_is_auditable(client, db_session, monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')

    simulated_hosts = [
        DiscoveredHost(ip_address="10.0.0.5", mac_address="AA:BB:CC:DD:EE:10", hostname="host-a"),
        DiscoveredHost(ip_address="10.0.0.6", mac_address="AA:BB:CC:DD:EE:11", hostname="host-b"),
    ]
    app.dependency_overrides[get_discovery_collector] = lambda: SimulatedCollector(simulated_hosts)

    try:
        token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)
        resp = client.post(
            "/api/v1/discovery/scans",
            headers={"Authorization": f"Bearer {token}"},
            json={"target_ranges": ["10.0.0.0/24"]},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "completed"
        assert body["hosts_discovered"] == 2
        assert body["new_assets"] == 2

        assets_resp = client.get("/api/v1/assets", headers={"Authorization": f"Bearer {token}"})
        assert assets_resp.status_code == 200
        assert len(assets_resp.json()) == 2

        from app.audit.models import AuditLog

        completed = db_session.query(AuditLog).filter_by(action="discovery.scan_completed").all()
        assert len(completed) == 1
    finally:
        app.dependency_overrides.pop(get_discovery_collector, None)
        settings_module.get_settings.cache_clear()


def test_scan_history_is_visible_to_any_authenticated_role(client, db_session, monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/8"]')
    app.dependency_overrides[get_discovery_collector] = lambda: SimulatedCollector([])

    try:
        admin_token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)
        client.post(
            "/api/v1/discovery/scans",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"target_ranges": ["10.0.0.0/24"]},
        )

        viewer_token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
        resp = client.get("/api/v1/discovery/scans", headers={"Authorization": f"Bearer {viewer_token}"})
        assert resp.status_code == 200
        assert len(resp.json()) == 1
    finally:
        app.dependency_overrides.pop(get_discovery_collector, None)
        settings_module.get_settings.cache_clear()


def test_scan_marks_missing_hosts_in_target_range_as_offline(client, db_session, monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["10.0.0.0/24"]')

    stale = Asset(
        ip_address="10.0.0.10",
        hostname="stale-host",
        status=AssetStatus.ONLINE,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db_session.add(stale)
    db_session.commit()

    app.dependency_overrides[get_discovery_collector] = lambda: SimulatedCollector([
        DiscoveredHost(ip_address="10.0.0.11", mac_address="AA:BB:CC:DD:EE:10", hostname="live-host")
    ])

    try:
        token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)
        resp = client.post(
            "/api/v1/discovery/scans",
            headers={"Authorization": f"Bearer {token}"},
            json={"target_ranges": ["10.0.0.0/24"]},
        )
        assert resp.status_code == 201

        refreshed = db_session.query(Asset).filter_by(ip_address="10.0.0.10").one()
        assert refreshed.status == AssetStatus.OFFLINE
    finally:
        app.dependency_overrides.pop(get_discovery_collector, None)
        settings_module.get_settings.cache_clear()


def test_scan_marks_assets_outside_current_scope_as_offline(client, db_session, monkeypatch):
    from app.config import settings as settings_module

    settings_module.get_settings.cache_clear()
    monkeypatch.setenv("AUTHORIZED_SCAN_RANGES", '["192.168.50.0/24"]')

    stale = Asset(
        ip_address="10.0.0.10",
        hostname="old-network-host",
        status=AssetStatus.ONLINE,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc),
    )
    db_session.add(stale)
    db_session.commit()

    app.dependency_overrides[get_discovery_collector] = lambda: SimulatedCollector([
        DiscoveredHost(ip_address="192.168.50.11", mac_address="AA:BB:CC:DD:EE:99", hostname="new-net-host")
    ])

    try:
        token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)
        resp = client.post(
            "/api/v1/discovery/scans",
            headers={"Authorization": f"Bearer {token}"},
            json={"target_ranges": ["192.168.50.0/24"]},
        )
        assert resp.status_code == 201

        refreshed = db_session.query(Asset).filter_by(ip_address="10.0.0.10").one()
        assert refreshed.status == AssetStatus.OFFLINE
    finally:
        app.dependency_overrides.pop(get_discovery_collector, None)
        settings_module.get_settings.cache_clear()
