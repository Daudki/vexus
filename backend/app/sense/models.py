import enum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.monitoring.models import MetricType


class BehavioralBaseline(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "behavioral_baselines"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    metric_type: Mapped[MetricType] = mapped_column(Enum(MetricType), index=True)

    sample_count: Mapped[int] = mapped_column(Integer, default=0)
    average_value: Mapped[float] = mapped_column(Float, default=0.0)
    stddev_value: Mapped[float] = mapped_column(Float, default=0.0)
    min_value: Mapped[float] = mapped_column(Float, default=0.0)
    max_value: Mapped[float] = mapped_column(Float, default=0.0)

    window_start: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=True)
    is_usable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[str] = mapped_column(String(512), default="")
