"""
Security Alert.

`dedup_key` groups repeats of the same underlying detection (typically
`f"{rule_key}:{asset_id}:{signature}"`, computed by the detection
service in Phase 5) so a device re-triggering the same rule every few
seconds produces one alert with an incrementing `occurrence_count`
instead of a flood of near-duplicate rows.
"""
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.events.models import EventSeverity


class AlertStatus(str, enum.Enum):
    NEW = "new"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    CLOSED = "closed"


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"

    rule_key: Mapped[str] = mapped_column(String(64), index=True)
    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)

    severity: Mapped[EventSeverity] = mapped_column(Enum(EventSeverity), default=EventSeverity.MEDIUM)
    confidence: Mapped[float] = mapped_column(default=1.0)
    status: Mapped[AlertStatus] = mapped_column(Enum(AlertStatus), default=AlertStatus.NEW)

    description: Mapped[str] = mapped_column(String(1024), default="")
    evidence: Mapped[str] = mapped_column(String(4096), default="[]")  # JSON-encoded NetworkEvent id list

    # --- Deduplication (accepted architectural addition) ---
    dedup_key: Mapped[str] = mapped_column(String(128), index=True)
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1)
    first_seen: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    suppressed: Mapped[bool] = mapped_column(Boolean, default=False)

    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
