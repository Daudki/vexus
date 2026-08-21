"""
MonitoringSample — historical time-series storage for Watch metrics.

One row per (asset, metric, timestamp). Kept deliberately narrow (one
value per row rather than a wide table) so new metric types can be
added without a schema migration — see MetricType.
"""
import enum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class MetricType(str, enum.Enum):
    AVAILABILITY = "availability"  # 1.0 = up, 0.0 = down
    LATENCY_MS = "latency_ms"
    PACKET_LOSS_PCT = "packet_loss_pct"


class MonitoringSample(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "monitoring_samples"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    metric_type: Mapped[MetricType] = mapped_column(Enum(MetricType), index=True)
    value: Mapped[float] = mapped_column(Float)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
