from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.assets.models import Asset
from app.risk.models import RiskFactor, RiskScore


class RiskRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_score(self, **kwargs) -> RiskScore:
        score = RiskScore(**kwargs)
        self.db.add(score)
        self.db.commit()
        self.db.refresh(score)
        return score

    def add_factor(self, **kwargs) -> RiskFactor:
        factor = RiskFactor(**kwargs)
        self.db.add(factor)
        self.db.commit()
        return factor

    def get_latest_for_asset(self, asset_id: str) -> RiskScore | None:
        query = select(RiskScore).where(RiskScore.asset_id == asset_id).order_by(desc(RiskScore.computed_at))
        return self.db.scalar(query)

    def get_factors(self, risk_score_id: str) -> list[RiskFactor]:
        query = select(RiskFactor).where(RiskFactor.risk_score_id == risk_score_id)
        return list(self.db.scalars(query))

    def get_history_for_asset(self, asset_id: str, limit: int = 50) -> list[RiskScore]:
        query = (
            select(RiskScore)
            .where(RiskScore.asset_id == asset_id)
            .order_by(desc(RiskScore.computed_at))
            .limit(limit)
        )
        return list(self.db.scalars(query))

    def get_top_risk_assets(self, limit: int = 10) -> list[Asset]:
        query = select(Asset).order_by(desc(Asset.risk_score)).limit(limit)
        return list(self.db.scalars(query))
