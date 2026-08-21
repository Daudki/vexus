from sqlalchemy import asc, desc, or_, select
from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetCriticality, AssetHistory, AssetStatus, AssetTrustStatus

_SORT_COLUMNS = {
    "last_seen": Asset.last_seen,
    "first_seen": Asset.first_seen,
    "risk_score": Asset.risk_score,
    "hostname": Asset.hostname,
}


class AssetRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, asset_id: str) -> Asset | None:
        return self.db.get(Asset, asset_id)

    def get_by_mac(self, mac_address: str) -> Asset | None:
        return self.db.scalar(select(Asset).where(Asset.mac_address == mac_address))

    def get_by_ip(self, ip_address: str) -> Asset | None:
        return self.db.scalar(select(Asset).where(Asset.ip_address == ip_address))

    def list_assets(
        self,
        *,
        search: str | None = None,
        status: AssetStatus | None = None,
        trust_status: AssetTrustStatus | None = None,
        criticality: AssetCriticality | None = None,
        sort_by: str = "last_seen",
        sort_desc: bool = True,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[Asset], int]:
        query = select(Asset)

        if search:
            like = f"%{search}%"
            query = query.where(or_(Asset.hostname.ilike(like), Asset.ip_address.ilike(like)))
        if status:
            query = query.where(Asset.status == status)
        if trust_status:
            query = query.where(Asset.trust_status == trust_status)
        if criticality:
            query = query.where(Asset.criticality == criticality)

        total = len(list(self.db.scalars(query)))

        sort_col = _SORT_COLUMNS.get(sort_by, Asset.last_seen)
        query = query.order_by(desc(sort_col) if sort_desc else asc(sort_col))
        query = query.limit(limit).offset(offset)

        return list(self.db.scalars(query)), total

    def create(self, **kwargs) -> Asset:
        asset = Asset(**kwargs)
        self.db.add(asset)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def update(self, asset: Asset, **kwargs) -> Asset:
        for key, value in kwargs.items():
            setattr(asset, key, value)
        self.db.commit()
        self.db.refresh(asset)
        return asset

    def add_history(self, **kwargs) -> AssetHistory:
        entry = AssetHistory(**kwargs)
        self.db.add(entry)
        self.db.commit()
        return entry

    def get_history(self, asset_id: str, limit: int = 100) -> list[AssetHistory]:
        query = (
            select(AssetHistory)
            .where(AssetHistory.asset_id == asset_id)
            .order_by(desc(AssetHistory.changed_at))
            .limit(limit)
        )
        return list(self.db.scalars(query))
