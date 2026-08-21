from datetime import datetime, timezone

from app.assets.models import Asset, AssetTrustStatus
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


def _seed_asset(db_session, ip_address, hostname=None):
    now = datetime.now(timezone.utc)
    asset = Asset(ip_address=ip_address, hostname=hostname, trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def test_viewer_can_read_graph_but_not_create_relationship(client, db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    b = _seed_asset(db_session, "10.0.0.2")
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)

    graph_resp = client.get("/api/v1/topology/graph", headers={"Authorization": f"Bearer {token}"})
    assert graph_resp.status_code == 200
    assert len(graph_resp.json()["nodes"]) == 2

    create_resp = client.post(
        "/api/v1/topology/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_asset_id": a.id, "target_asset_id": b.id, "relationship_type": "uplink"},
    )
    assert create_resp.status_code == 403


def test_security_analyst_can_create_and_delete_relationship(client, db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    b = _seed_asset(db_session, "10.0.0.2")
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    create_resp = client.post(
        "/api/v1/topology/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_asset_id": a.id, "target_asset_id": b.id, "relationship_type": "uplink", "description": "core link"},
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["confidence"] == "confirmed"

    delete_resp = client.delete(
        f"/api/v1/topology/relationships/{body['id']}", headers={"Authorization": f"Bearer {token}"}
    )
    assert delete_resp.status_code == 204

    list_resp = client.get("/api/v1/topology/relationships", headers={"Authorization": f"Bearer {token}"})
    assert list_resp.json() == []


def test_self_loop_relationship_returns_400(client, db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    resp = client.post(
        "/api/v1/topology/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_asset_id": a.id, "target_asset_id": a.id, "relationship_type": "uplink"},
    )
    assert resp.status_code == 400


def test_viewer_cannot_trigger_subnet_inference(client, db_session):
    token = _create_and_login(client, db_session, "viewer1", RoleName.VIEWER)
    resp = client.post(
        "/api/v1/topology/infer-subnet", headers={"Authorization": f"Bearer {token}"}, json={"prefix_length": 24}
    )
    assert resp.status_code == 403


def test_network_admin_can_trigger_subnet_inference(client, db_session):
    _seed_asset(db_session, "10.0.0.5")
    _seed_asset(db_session, "10.0.0.6")
    token = _create_and_login(client, db_session, "netadmin1", RoleName.NETWORK_ADMINISTRATOR)

    resp = client.post(
        "/api/v1/topology/infer-subnet", headers={"Authorization": f"Bearer {token}"}, json={"prefix_length": 24}
    )
    assert resp.status_code == 200
    assert resp.json()["relationships_created"] == 1

    graph_resp = client.get("/api/v1/topology/graph", headers={"Authorization": f"Bearer {token}"})
    assert len(graph_resp.json()["edges"]) == 1
    assert graph_resp.json()["edges"][0]["confidence"] == "inferred"


def test_delete_nonexistent_relationship_returns_404(client, db_session):
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)
    resp = client.delete(
        "/api/v1/topology/relationships/does-not-exist", headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 404


def test_relationships_can_be_filtered_by_asset(client, db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    b = _seed_asset(db_session, "10.0.0.2")
    c = _seed_asset(db_session, "10.0.0.3")
    token = _create_and_login(client, db_session, "analyst1", RoleName.SECURITY_ANALYST)

    client.post(
        "/api/v1/topology/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_asset_id": a.id, "target_asset_id": b.id, "relationship_type": "uplink"},
    )
    client.post(
        "/api/v1/topology/relationships",
        headers={"Authorization": f"Bearer {token}"},
        json={"source_asset_id": b.id, "target_asset_id": c.id, "relationship_type": "downlink"},
    )

    resp = client.get(f"/api/v1/topology/relationships?asset_id={a.id}", headers={"Authorization": f"Bearer {token}"})
    assert len(resp.json()) == 1
