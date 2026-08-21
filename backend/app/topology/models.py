"""
AssetRelationship — VEXUS Nexus.

Every relationship carries a mandatory `confidence` classification.
There is no "confirmed by default" path: manual relationships are
confirmed because an analyst asserted them (and that assertion is
audited); inferred relationships are inferred because they were
computed from real observed data (currently: shared IP subnet), never
fabricated. Nothing in this module invents a relationship VEXUS has no
evidence for — in particular, there is no "communicates with" edge,
because VEXUS does not capture network traffic in any phase built so
far. That's a real gap, not something papered over here.
"""
import enum

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class RelationshipConfidence(str, enum.Enum):
    CONFIRMED = "confirmed"  # analyst-asserted
    INFERRED = "inferred"    # computed from observed evidence (e.g. shared subnet)
    UNKNOWN = "unknown"      # reserved for future collectors that can't yet classify


class AssetRelationship(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "asset_relationships"

    source_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    target_asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)

    # Free-text-ish but conventionally one of: "same_subnet", "uplink",
    # "downlink", "manual_link" — not a strict enum because real network
    # topology vocabulary varies more than a fixed set can capture cleanly.
    relationship_type: Mapped[str] = mapped_column(String(64), index=True)

    confidence: Mapped[RelationshipConfidence] = mapped_column(Enum(RelationshipConfidence))
    description: Mapped[str] = mapped_column(String(512), default="")

    created_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    first_observed: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    last_observed: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
