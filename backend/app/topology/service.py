"""
Topology application service.

`infer_subnet_relationships` is the only automated relationship builder
in V1. It groups assets by IP subnet and records an INFERRED
"same_subnet" edge for each pair sharing one — genuinely observed
evidence (the IP addresses VEXUS already has), not a guess. It is
idempotent: rerunning it updates `last_observed` on existing edges
rather than duplicating them.
"""
import ipaddress
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.assets.models import Asset
from app.audit.service import AuditService
from app.topology.models import AssetRelationship, RelationshipConfidence
from app.topology.repository import TopologyRepository
from app.users.models import User

SAME_SUBNET = "same_subnet"


class TopologyError(Exception):
    pass


@dataclass
class InferenceSummary:
    subnets_examined: int
    relationships_created: int
    relationships_updated: int


class TopologyService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TopologyRepository(db)
        self.audit = AuditService(db)

    # --- Manual relationships (analyst-asserted, always CONFIRMED) ---

    def create_manual_relationship(
        self,
        *,
        source_asset_id: str,
        target_asset_id: str,
        relationship_type: str,
        description: str,
        actor: User,
        ip_address: str = "",
    ) -> AssetRelationship:
        if source_asset_id == target_asset_id:
            raise TopologyError("An asset cannot have a relationship with itself.")

        if self.db.get(Asset, source_asset_id) is None:
            raise TopologyError(f"Source asset '{source_asset_id}' does not exist.")
        if self.db.get(Asset, target_asset_id) is None:
            raise TopologyError(f"Target asset '{target_asset_id}' does not exist.")

        now = datetime.now(timezone.utc)
        rel = self.repo.create(
            source_asset_id=source_asset_id,
            target_asset_id=target_asset_id,
            relationship_type=relationship_type,
            confidence=RelationshipConfidence.CONFIRMED,
            description=description,
            created_by_user_id=actor.id,
            first_observed=now,
            last_observed=now,
        )

        self.audit.record(
            action="topology.relationship_created",
            actor=actor,
            target_type="asset_relationship",
            target_id=rel.id,
            detail=f"{relationship_type}: {source_asset_id} -> {target_asset_id}",
            ip_address=ip_address,
        )
        return rel

    def delete_relationship(self, relationship_id: str, actor: User, ip_address: str = "") -> None:
        rel = self.repo.get_by_id(relationship_id)
        if rel is None:
            raise TopologyError("Relationship not found.")

        self.audit.record(
            action="topology.relationship_deleted",
            actor=actor,
            target_type="asset_relationship",
            target_id=rel.id,
            detail=f"{rel.relationship_type}: {rel.source_asset_id} -> {rel.target_asset_id}",
            ip_address=ip_address,
        )
        self.repo.delete(rel)

    # --- Inference (evidence-based, always INFERRED) ---

    def infer_subnet_relationships(self, prefix_length: int = 24, actor: User | None = None, ip_address: str = "") -> InferenceSummary:
        now = datetime.now(timezone.utc)
        assets_with_ip = [a for a in self.db.query(Asset).all() if a.ip_address]

        subnets: dict[str, list[Asset]] = {}
        for asset in assets_with_ip:
            try:
                network = ipaddress.ip_network(f"{asset.ip_address}/{prefix_length}", strict=False)
            except ValueError:
                continue  # skip unparseable addresses rather than guessing
            subnets.setdefault(str(network), []).append(asset)

        created = 0
        updated = 0

        for members in subnets.values():
            if len(members) < 2:
                continue
            for i in range(len(members)):
                for j in range(i + 1, len(members)):
                    a, b = members[i], members[j]
                    existing = self.repo.find(a.id, b.id, SAME_SUBNET)
                    if existing is None:
                        self.repo.create(
                            source_asset_id=a.id,
                            target_asset_id=b.id,
                            relationship_type=SAME_SUBNET,
                            confidence=RelationshipConfidence.INFERRED,
                            description=f"Both assets observed on the same /{prefix_length} subnet.",
                            created_by_user_id=None,
                            first_observed=now,
                            last_observed=now,
                        )
                        created += 1
                    else:
                        self.repo.update_last_observed(existing, now)
                        updated += 1

        if actor is not None:
            self.audit.record(
                action="topology.subnet_inference_run",
                actor=actor,
                detail=f"{len(subnets)} subnets examined, {created} created, {updated} updated",
                ip_address=ip_address,
            )

        return InferenceSummary(
            subnets_examined=len(subnets), relationships_created=created, relationships_updated=updated
        )

    # --- Graph assembly ---

    def get_graph(self) -> dict:
        assets = self.db.query(Asset).all()
        relationships = self.repo.list_all()

        nodes = [
            {
                "id": a.id,
                "hostname": a.hostname,
                "ip_address": a.ip_address,
                "device_type": a.device_type,
                "status": a.status.value,
                "criticality": a.criticality.value,
                "trust_status": a.trust_status.value,
            }
            for a in assets
        ]
        edges = [
            {
                "id": r.id,
                "source": r.source_asset_id,
                "target": r.target_asset_id,
                "relationship_type": r.relationship_type,
                "confidence": r.confidence.value,
            }
            for r in relationships
        ]
        return {"nodes": nodes, "edges": edges}
