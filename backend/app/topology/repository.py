from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.topology.models import AssetRelationship


class TopologyRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, relationship_id: str) -> AssetRelationship | None:
        return self.db.get(AssetRelationship, relationship_id)

    def find(
        self, source_asset_id: str, target_asset_id: str, relationship_type: str
    ) -> AssetRelationship | None:
        """Order-independent lookup — used to keep inference idempotent
        (A-B and B-A are the same edge for an undirected relationship type
        like same_subnet)."""
        query = select(AssetRelationship).where(
            AssetRelationship.relationship_type == relationship_type,
            or_(
                and_(
                    AssetRelationship.source_asset_id == source_asset_id,
                    AssetRelationship.target_asset_id == target_asset_id,
                ),
                and_(
                    AssetRelationship.source_asset_id == target_asset_id,
                    AssetRelationship.target_asset_id == source_asset_id,
                ),
            ),
        )
        return self.db.scalar(query)

    def list_all(self, asset_id: str | None = None) -> list[AssetRelationship]:
        query = select(AssetRelationship)
        if asset_id:
            query = query.where(
                or_(
                    AssetRelationship.source_asset_id == asset_id,
                    AssetRelationship.target_asset_id == asset_id,
                )
            )
        return list(self.db.scalars(query))

    def create(self, **kwargs) -> AssetRelationship:
        rel = AssetRelationship(**kwargs)
        self.db.add(rel)
        self.db.commit()
        self.db.refresh(rel)
        return rel

    def update_last_observed(self, rel: AssetRelationship, when) -> AssetRelationship:
        rel.last_observed = when
        self.db.commit()
        self.db.refresh(rel)
        return rel

    def delete(self, rel: AssetRelationship) -> None:
        self.db.delete(rel)
        self.db.commit()
