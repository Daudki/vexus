"""
Detection rule configuration.

Rule *logic* is code (a `DetectionRule` class implementing
`evaluate(events) -> Finding[]`, landing in Phase 5). This table holds
the *tunable* parameters so an analyst can enable/disable a rule or
adjust its thresholds without a redeploy.

`rule_key` is the stable identifier a `DetectionRule` class registers
itself under (e.g. "new_device_detection") — not a display name.
"""
from sqlalchemy import Boolean, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.events.models import EventSeverity


class DetectionRuleConfig(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "detection_rule_configs"

    rule_key: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")

    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    severity: Mapped[EventSeverity] = mapped_column(default=EventSeverity.MEDIUM)
    confidence_threshold: Mapped[float] = mapped_column(Float, default=0.80)
    alert_threshold: Mapped[int] = mapped_column(Integer, default=1)  # events required to raise an alert
    suppression_window_minutes: Mapped[int] = mapped_column(Integer, default=30)
