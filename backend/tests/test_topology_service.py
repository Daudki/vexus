from datetime import datetime, timezone

import pytest

from app.assets.models import Asset, AssetTrustStatus
from app.core.security import hash_password
from app.topology.models import RelationshipConfidence
from app.topology.service import TopologyError, TopologyService
from app.users.models import Role, RoleName, User


def _seed_asset(db_session, ip_address, hostname=None):
    now = datetime.now(timezone.utc)
    asset = Asset(
        ip_address=ip_address,
        hostname=hostname,
        trust_status=AssetTrustStatus.UNKNOWN,
        first_seen=now,
        last_seen=now,
    )
    db_session.add(asset)
    db_session.commit()
    db_session.refresh(asset)
    return asset


def _seed_user(db_session, username="admin1", role_name=RoleName.ADMIN):
    role = db_session.query(Role).filter_by(name=role_name).first()
    user = User(
        username=username,
        email=f"{username}@vexus.local",
        password_hash=hash_password("Password123!"),
        role_id=role.id,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_manual_relationship_is_always_confirmed(db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    b = _seed_asset(db_session, "10.0.0.2")
    actor = _seed_user(db_session)

    rel = TopologyService(db_session).create_manual_relationship(
        source_asset_id=a.id,
        target_asset_id=b.id,
        relationship_type="uplink",
        description="a uplinks to b",
        actor=actor,
    )

    assert rel.confidence == RelationshipConfidence.CONFIRMED


def test_manual_relationship_rejects_self_loop(db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    actor = _seed_user(db_session)

    with pytest.raises(TopologyError, match="cannot have a relationship with itself"):
        TopologyService(db_session).create_manual_relationship(
            source_asset_id=a.id,
            target_asset_id=a.id,
            relationship_type="uplink",
            description="",
            actor=actor,
        )


def test_manual_relationship_rejects_nonexistent_asset(db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    actor = _seed_user(db_session)

    with pytest.raises(TopologyError, match="does not exist"):
        TopologyService(db_session).create_manual_relationship(
            source_asset_id=a.id,
            target_asset_id="does-not-exist",
            relationship_type="uplink",
            description="",
            actor=actor,
        )


def test_manual_relationship_is_audited(db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    b = _seed_asset(db_session, "10.0.0.2")
    actor = _seed_user(db_session)

    TopologyService(db_session).create_manual_relationship(
        source_asset_id=a.id, target_asset_id=b.id, relationship_type="uplink", description="", actor=actor
    )

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="topology.relationship_created").all()
    assert len(entries) == 1


def test_subnet_inference_links_assets_in_same_subnet(db_session):
    a = _seed_asset(db_session, "10.0.0.5")
    b = _seed_asset(db_session, "10.0.0.6")
    c = _seed_asset(db_session, "192.168.1.5")  # different subnet

    summary = TopologyService(db_session).infer_subnet_relationships(prefix_length=24)

    assert summary.relationships_created == 1  # only a<->b, c is isolated

    from app.topology.repository import TopologyRepository

    repo = TopologyRepository(db_session)
    assert repo.find(a.id, b.id, "same_subnet") is not None
    assert repo.find(a.id, c.id, "same_subnet") is None


def test_subnet_inference_relationship_has_inferred_confidence(db_session):
    a = _seed_asset(db_session, "10.0.0.5")
    b = _seed_asset(db_session, "10.0.0.6")

    TopologyService(db_session).infer_subnet_relationships(prefix_length=24)

    from app.topology.repository import TopologyRepository

    rel = TopologyRepository(db_session).find(a.id, b.id, "same_subnet")
    assert rel.confidence == RelationshipConfidence.INFERRED


def test_subnet_inference_is_idempotent(db_session):
    a = _seed_asset(db_session, "10.0.0.5")
    b = _seed_asset(db_session, "10.0.0.6")
    service = TopologyService(db_session)

    first = service.infer_subnet_relationships(prefix_length=24)
    second = service.infer_subnet_relationships(prefix_length=24)

    assert first.relationships_created == 1
    assert second.relationships_created == 0
    assert second.relationships_updated == 1  # existing edge's last_observed refreshed, not duplicated

    from app.topology.repository import TopologyRepository

    all_rels = TopologyRepository(db_session).list_all()
    assert len(all_rels) == 1


def test_subnet_inference_skips_assets_without_ip(db_session):
    now = datetime.now(timezone.utc)
    a = Asset(ip_address=None, mac_address="AA:BB:CC:DD:EE:01", trust_status=AssetTrustStatus.UNKNOWN, first_seen=now, last_seen=now)
    b = _seed_asset(db_session, "10.0.0.6")
    db_session.add(a)
    db_session.commit()

    summary = TopologyService(db_session).infer_subnet_relationships(prefix_length=24)

    assert summary.relationships_created == 0  # only one asset has an IP, no pair to link


def test_delete_relationship_is_audited(db_session):
    a = _seed_asset(db_session, "10.0.0.1")
    b = _seed_asset(db_session, "10.0.0.2")
    actor = _seed_user(db_session)
    service = TopologyService(db_session)

    rel = service.create_manual_relationship(
        source_asset_id=a.id, target_asset_id=b.id, relationship_type="uplink", description="", actor=actor
    )
    service.delete_relationship(rel.id, actor=actor)

    assert service.repo.get_by_id(rel.id) is None

    from app.audit.models import AuditLog

    entries = db_session.query(AuditLog).filter_by(action="topology.relationship_deleted").all()
    assert len(entries) == 1


def test_get_graph_returns_nodes_and_edges(db_session):
    a = _seed_asset(db_session, "10.0.0.5", hostname="host-a")
    b = _seed_asset(db_session, "10.0.0.6", hostname="host-b")
    TopologyService(db_session).infer_subnet_relationships(prefix_length=24)

    graph = TopologyService(db_session).get_graph()

    assert len(graph["nodes"]) == 2
    assert len(graph["edges"]) == 1
    assert graph["edges"][0]["confidence"] == "inferred"
