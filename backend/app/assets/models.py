import enum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AssetStatus(str, enum.Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


class AssetTrustStatus(str, enum.Enum):
    TRUSTED = "trusted"
    UNKNOWN = "unknown"
    UNTRUSTED = "untrusted"


class AssetCriticality(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Asset(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assets"

    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True, index=True)
    mac_address: Mapped[str | None] = mapped_column(String(17), nullable=True, index=True)
    hostname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    operating_system: Mapped[str | None] = mapped_column(String(128), nullable=True)
    vendor: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[AssetStatus] = mapped_column(Enum(AssetStatus), default=AssetStatus.UNKNOWN)
    criticality: Mapped[AssetCriticality] = mapped_column(Enum(AssetCriticality), default=AssetCriticality.LOW)
    trust_status: Mapped[AssetTrustStatus] = mapped_column(Enum(AssetTrustStatus), default=AssetTrustStatus.UNKNOWN)

    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    first_seen: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    risk_score: Mapped[float] = mapped_column(Float, default=0.0)  # populated by the Risk module (Phase 6)
    # Simulation Mode (docs/vexus-v2.md, domain 14): a simulated asset
    # must remain identifiable and must never be mixed silently with
    # real inventory. Matches the same flag already present on
    # NetworkEvent/Alert/Incident.
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)

    @property
    def display_name(self) -> str:
        return self.hostname or self.ip_address or self.mac_address or self.id


class AssetChangeType(str, enum.Enum):
    FIRST_DISCOVERED = "first_discovered"
    IP_CHANGED = "ip_changed"
    MAC_CHANGED = "mac_changed"
    HOSTNAME_CHANGED = "hostname_changed"
    STATUS_CHANGED = "status_changed"
    RISK_CHANGED = "risk_changed"
    METADATA_CHANGED = "metadata_changed"


class AssetHistory(UUIDPrimaryKeyMixin, Base):
    """
    Append-only change log for an asset. Every field change discovery (or,
    later, an analyst edit) makes to an Asset writes one row here — this is
    what lets Trace/AI answer "what changed on this device and when."
    """
    __tablename__ = "asset_history"

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    change_type: Mapped[AssetChangeType] = mapped_column(Enum(AssetChangeType))
    previous_value: Mapped[str] = mapped_column(String(512), default="")
    new_value: Mapped[str] = mapped_column(String(512), default="")
    source: Mapped[str] = mapped_column(String(64), default="discovery")  # discovery | manual | monitoring
    changed_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
