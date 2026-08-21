"""
RiskScore / RiskFactor — VEXUS Risk.

Every score is a sum of named RiskFactor rows, never a bare number.
A recompute writes a brand-new RiskScore rather than updating one in
place, so risk trends over time (Trace/AI can later answer "when did
this asset's risk start climbing" without a separate history table).
`Asset.risk_score` is kept in sync with the latest computation so
existing list/detail views (built in Phase 2, before Risk existed)
don't need to change to show it.
"""
import enum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class RiskLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RiskScore(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "risk_scores"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    score: Mapped[float] = mapped_column(Float)  # 0-100
    risk_level: Mapped[RiskLevel] = mapped_column(Enum(RiskLevel))
    computed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class RiskFactor(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "risk_factors"

    risk_score_id: Mapped[str] = mapped_column(ForeignKey("risk_scores.id"), index=True)
    factor_key: Mapped[str] = mapped_column(String(64))  # e.g. "criticality", "trust_status", "alert"
    label: Mapped[str] = mapped_column(String(255))
    points: Mapped[float] = mapped_column(Float)
    description: Mapped[str] = mapped_column(String(512), default="")
