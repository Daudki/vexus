"""
NetworkEvent — the VEXUS Data Contract.

Every module that observes something (discovery, monitoring, and later
syslog/threat-intel/identity) writes a NetworkEvent in this exact shape.
Nothing downstream (Detection, Correlation, Risk) reads from any other
table. `correlation_id` and `parent_event_id` are unused by anything in
V1 but present now so V2's Correlate module doesn't require a migration.

`is_synthetic` is non-nullable and defaults to False; Simulation Mode is
the only writer that ever sets it True. This flag is expected to
propagate to Finding/Alert/Incident so simulated data can never be
mistaken for real telemetry (see architecture doc, "Simulation Mode").
"""
import enum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, UUIDPrimaryKeyMixin


class EventSeverity(str, enum.Enum):
    INFORMATIONAL = "informational"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class EventSource(str, enum.Enum):
    DISCOVERY = "discovery"
    MONITORING = "monitoring"
    SYSLOG = "syslog"
    THREAT_INTEL = "threat_intel"
    IDENTITY = "identity"
    SIMULATION = "simulation"
    MANUAL = "manual"


class NetworkEvent(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "network_events"

    event_type: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "NEW_DEVICE"
    event_source: Mapped[EventSource] = mapped_column(Enum(EventSource), index=True)
    timestamp: Mapped[DateTime] = mapped_column(DateTime(timezone=True), index=True)

    asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True, index=True)
    source_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)
    destination_asset_id: Mapped[str | None] = mapped_column(ForeignKey("assets.id"), nullable=True)

    severity: Mapped[EventSeverity] = mapped_column(Enum(EventSeverity), default=EventSeverity.INFORMATIONAL)
    confidence: Mapped[float] = mapped_column(Float, default=1.0)  # 0.0 - 1.0

    description: Mapped[str] = mapped_column(String(1024), default="")
    evidence: Mapped[str] = mapped_column(String(4096), default="[]")  # JSON-encoded evidence list
    event_metadata: Mapped[str] = mapped_column(String(4096), default="{}")  # JSON-encoded

    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    parent_event_id: Mapped[str | None] = mapped_column(ForeignKey("network_events.id"), nullable=True)

    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    processed_by_detection: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
