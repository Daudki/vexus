"""
Incident and related models — VEXUS Trace.

Every Incident in V1 is analyst-created: Correlate (which would
auto-generate "incident candidates" from correlated alerts) is
deferred to V2, so there's no automated path that creates an Incident
here. IncidentAlert/IncidentAsset are explicit link tables (not a bare
SQLAlchemy secondary relationship) specifically so each link carries
its own `linked_at` timestamp — that timestamp is what lets the
timeline show "when did we connect this evidence to the incident",
not just "what's connected now".

InvestigationNote is append-only by convention, same as AuditLog: no
update/delete endpoint exists anywhere in the codebase.
"""
import enum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.events.models import EventSeverity


class IncidentStatus(str, enum.Enum):
    OPEN = "open"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"
    CLOSED = "closed"


class Incident(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "incidents"

    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(String(2048), default="")
    severity: Mapped[EventSeverity] = mapped_column(Enum(EventSeverity))
    confidence: Mapped[float] = mapped_column(Float)
    status: Mapped[IncidentStatus] = mapped_column(Enum(IncidentStatus), default=IncidentStatus.OPEN)
    assigned_to: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    resolution: Mapped[str] = mapped_column(String(2048), default="")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class IncidentAlert(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "incident_alerts"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    alert_id: Mapped[str] = mapped_column(ForeignKey("alerts.id"), index=True)
    linked_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))


class IncidentAsset(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "incident_assets"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    asset_id: Mapped[str] = mapped_column(ForeignKey("assets.id"), index=True)
    linked_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))


class InvestigationNote(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "investigation_notes"

    incident_id: Mapped[str] = mapped_column(ForeignKey("incidents.id"), index=True)
    author_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_username: Mapped[str] = mapped_column(String(64))  # denormalized snapshot, like AuditLog
    content: Mapped[str] = mapped_column(String(4096))
