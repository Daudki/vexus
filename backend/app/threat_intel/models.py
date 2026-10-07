"""Persistent threat-intelligence records.

VEXUS keeps a normalized vulnerability record separate from the raw provider
payload. Provider-specific adapters populate this model; downstream services
never need to understand NVD's wire format.
"""
import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class Vulnerability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "vulnerabilities"

    cve_id: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    cvss_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    cvss_severity: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    cvss_version: Mapped[str | None] = mapped_column(String(8), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    last_modified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    cwe_ids: Mapped[str] = mapped_column(Text, default="[]")
    affected_cpes: Mapped[str] = mapped_column(Text, default="[]")
    references: Mapped[str] = mapped_column(Text, default="[]")
    raw_data: Mapped[str] = mapped_column(Text, default="{}")
    is_rejected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)


class VulnerabilityMatchConfidence(str, enum.Enum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"


class AssetVulnerability(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_vulnerabilities"
    __table_args__ = (UniqueConstraint("asset_id", "vulnerability_id", name="uq_asset_vulnerability"),)

    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    vulnerability_id: Mapped[str] = mapped_column(ForeignKey("vulnerabilities.id"), index=True)
    confidence: Mapped[VulnerabilityMatchConfidence] = mapped_column(
        Enum(VulnerabilityMatchConfidence, name="vulnerability_match_confidence")
    )
    match_source: Mapped[str] = mapped_column(String(32), index=True)
    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
