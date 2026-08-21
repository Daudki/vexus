from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.risk.models import RiskLevel


class RiskFactorRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    factor_key: str
    label: str
    points: float
    description: str


class RiskScoreRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    asset_id: str
    score: float
    risk_level: RiskLevel
    computed_at: datetime
    factors: list[RiskFactorRead] = []


class RiskScoreHistoryEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    score: float
    risk_level: RiskLevel
    computed_at: datetime


class RecomputeSummaryRead(BaseModel):
    assets_scored: int
    average_score: float
    detection_data_stale: bool


class TopRiskAssetRead(BaseModel):
    id: str
    hostname: str | None
    ip_address: str | None
    risk_score: float
    criticality: str
    trust_status: str
