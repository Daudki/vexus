from datetime import datetime, timezone

from app.assets.models import Asset, AssetCriticality, AssetTrustStatus
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


def _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.UNKNOWN):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address="10.0.0.40", criticality=criticality, trust_status=trust_status, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_viewer_cannot_trigger_recompute(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post("/api/v1/risk/recompute", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403


def test_get_risk_for_asset_with_no_score_yet_returns_404(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    resp = client.get(f"/api/v1/risk/assets/{asset.id}", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_analyst_can_recompute_all_and_then_read_scores(client, db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.CRITICAL, trust_status=AssetTrustStatus.UNTRUSTED)
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    recompute_resp = client.post("/api/v1/risk/recompute", headers={"Authorization": f"Bearer {token}"})
    assert recompute_resp.status_code == 200
    assert recompute_resp.json()["assets_scored"] == 1
    assert recompute_resp.json()["detection_data_stale"] is True  # detection never ran in this test

    score_resp = client.get(f"/api/v1/risk/assets/{asset.id}", headers={"Authorization": f"Bearer {token}"})
    assert score_resp.status_code == 200
    body = score_resp.json()
    assert body["score"] == 50
    assert body["risk_level"] == "high"
    assert len(body["factors"]) >= 2


def test_per_asset_recompute_endpoint(client, db_session):
    asset = _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.TRUSTED)
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)

    resp = client.post(f"/api/v1/risk/assets/{asset.id}/recompute", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["score"] == 0


def test_recompute_nonexistent_asset_returns_404(client, db_session):
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)
    resp = client.post("/api/v1/risk/assets/does-not-exist/recompute", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 404


def test_top_risk_assets_are_ordered_by_score_descending(client, db_session):
    _seed_asset(db_session, criticality=AssetCriticality.LOW, trust_status=AssetTrustStatus.TRUSTED)
    _seed_asset(db_session, criticality=AssetCriticality.CRITICAL, trust_status=AssetTrustStatus.UNTRUSTED)
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)

    client.post("/api/v1/risk/recompute", headers={"Authorization": f"Bearer {token}"})

    resp = client.get("/api/v1/risk/top", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    scores = [a["risk_score"] for a in resp.json()]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] == 50


def test_risk_history_accumulates_across_recomputes(client, db_session):
    asset = _seed_asset(db_session)
    token = _create_and_login(client, db_session, "admin1", RoleName.ADMIN)

    client.post(f"/api/v1/risk/assets/{asset.id}/recompute", headers={"Authorization": f"Bearer {token}"})
    client.post(f"/api/v1/risk/assets/{asset.id}/recompute", headers={"Authorization": f"Bearer {token}"})

    resp = client.get(f"/api/v1/risk/assets/{asset.id}/history", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2
