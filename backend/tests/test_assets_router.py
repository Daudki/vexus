from datetime import datetime, timezone

from app.assets.models import Asset, AssetCriticality, AssetStatus, AssetTrustStatus
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


def _seed_asset(db_session, **overrides):
    now = datetime.now(timezone.utc)
    defaults = dict(
        ip_address="10.0.0.50",
        hostname="seed-host",
        status=AssetStatus.ONLINE,
        trust_status=AssetTrustStatus.UNKNOWN,
        criticality=AssetCriticality.LOW,
        first_seen=now,
        last_seen=now,
    )
    defaults.update(overrides)
    asset = Asset(**defaults)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_list_assets_requires_authentication(client):
    resp = client.get("/api/v1/assets")
    assert resp.status_code == 401


def test_viewer_can_list_but_not_update_assets(client, db_session):
    _seed_asset(db_session)
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    list_resp = client.get("/api/v1/assets", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    asset_id = list_resp.json()[0]["id"]
    update_resp = client.patch(
        f"/api/v1/assets/{asset_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"criticality": "high"},
    )
    assert update_resp.status_code == 403


def test_security_analyst_can_update_asset_and_it_is_audited(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    resp = client.patch(
        f"/api/v1/assets/{asset.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"criticality": "critical", "trust_status": "trusted", "owner": "IT Team"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["criticality"] == "critical"
    assert body["trust_status"] == "trusted"
    assert body["owner"] == "IT Team"

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="asset.update").all()
    assert len(entries) == 1


def test_asset_update_writes_history_entry(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    client.patch(
        f"/api/v1/assets/{asset.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"criticality": "high"},
    )

    history_resp = client.get(f"/api/v1/assets/{asset.id}/history", headers={"Authorization": f"Bearer {token}"})
    assert history_resp.status_code == 200
    assert len(history_resp.json()) == 1
    assert history_resp.json()[0]["change_type"] == "metadata_changed"


def test_search_filters_by_hostname(client, db_session):
    _seed_asset(db_session, ip_address="10.0.0.51", hostname="router-core")
    _seed_asset(db_session, ip_address="10.0.0.52", hostname="printer-lobby")
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    resp = client.get("/api/v1/assets?search=router", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 1
    assert resp.json()[0]["hostname"] == "router-core"


def test_unknown_asset_is_not_flagged_untrusted_by_default(client, db_session):
    _seed_asset(db_session)
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/assets", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()[0]["trust_status"] == "unknown"


def test_asset_display_name_falls_back_to_ip_when_hostname_missing(client, db_session):
    _seed_asset(db_session, hostname=None, ip_address="10.0.0.77")
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    resp = client.get("/api/v1/assets", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()[0]["display_name"] == "10.0.0.77"


def test_get_nonexistent_asset_returns_404(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.get("/api/v1/assets/does-not-exist", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404
