"""
Incident application service.

`create_incident` is the only entry point that produces an Incident,
and it always requires at least one linked Alert or Asset — an
incident about nothing isn't representable. Linking an alert also
auto-links that alert's asset (if it has one) as an affected asset, so
"affected assets" stays accurate without the analyst re-entering
something VEXUS already knows.

`get_timeline` never invents entries: it only reads NetworkEvents
already referenced by a linked alert's evidence, InvestigationNotes
attached to this incident, and this incident's own AuditLog trail.
"""
import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.alerts.models import Alert
from app.assets.models import Asset
from app.audit.models import AuditLog
from app.audit.service import AuditService
from app.events.models import EventSeverity, NetworkEvent
from app.incidents.models import Incident, IncidentStatus, InvestigationNote
from app.incidents.repository import IncidentRepository
from app.users.models import User

_SEVERITY_ORDER = [
    EventSeverity.INFORMATIONAL,
    EventSeverity.LOW,
    EventSeverity.MEDIUM,
    EventSeverity.HIGH,
    EventSeverity.CRITICAL,
]


class IncidentError(Exception):
    pass


@dataclass
class TimelineEntry:
    timestamp: datetime
    kind: str  # "event" | "note" | "audit"
    summary: str
    detail: str


class IncidentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = IncidentRepository(db)
        self.audit = AuditService(db)

    def create_incident(
        self,
        *,
        title: str,
        description: str,
        alert_ids: list[str],
        asset_ids: list[str],
        actor: User,
        severity: EventSeverity | None = None,
        confidence: float | None = None,
        ip_address: str = "",
    ) -> Incident:
        if not alert_ids and not asset_ids:
            raise IncidentError("An incident needs at least one linked alert or asset.")

        alerts = []
        for alert_id in alert_ids:
            alert = self.db.get(Alert, alert_id)
            if alert is None:
                raise IncidentError(f"Alert '{alert_id}' does not exist.")
            alerts.append(alert)

        for asset_id in asset_ids:
            if self.db.get(Asset, asset_id) is None:
                raise IncidentError(f"Asset '{asset_id}' does not exist.")

        if severity is None:
            severity = self._max_severity([a.severity for a in alerts]) if alerts else EventSeverity.MEDIUM
        if confidence is None:
            confidence = (sum(a.confidence for a in alerts) / len(alerts)) if alerts else 0.5

        now = datetime.now(timezone.utc)
        incident = self.repo.create(
            title=title,
            description=description,
            severity=severity,
            confidence=confidence,
            status=IncidentStatus.OPEN,
            is_synthetic=False,
        )

        for alert in alerts:
            self._link_alert_internal(incident.id, alert, now)

        already_linked_asset_ids = {link.asset_id for link in self.repo.list_asset_links(incident.id)}
        for asset_id in asset_ids:
            if asset_id not in already_linked_asset_ids:
                self.repo.link_asset(incident.id, asset_id, now)
                already_linked_asset_ids.add(asset_id)

        self.audit.record(
            action="incident.created",
            actor=actor,
            target_type="incident",
            target_id=incident.id,
            detail=f"'{title}' — {len(alerts)} alert(s), {len(already_linked_asset_ids)} asset(s)",
            ip_address=ip_address,
        )
        return incident

    def _link_alert_internal(self, incident_id: str, alert: Alert, when: datetime) -> None:
        self.repo.link_alert(incident_id, alert.id, when)
        if alert.asset_id and self.repo.get_asset_link(incident_id, alert.asset_id) is None:
            self.repo.link_asset(incident_id, alert.asset_id, when)

    @staticmethod
    def _max_severity(severities: list[EventSeverity]) -> EventSeverity:
        return max(severities, key=_SEVERITY_ORDER.index)

    # --- Linking (analyst corrections after creation) ---

    def link_alert(self, incident: Incident, alert_id: str, actor: User, ip_address: str = "") -> None:
        alert = self.db.get(Alert, alert_id)
        if alert is None:
            raise IncidentError(f"Alert '{alert_id}' does not exist.")
        if self.repo.get_alert_link(incident.id, alert_id) is not None:
            raise IncidentError("This alert is already linked to the incident.")

        now = datetime.now(timezone.utc)
        self._link_alert_internal(incident.id, alert, now)
        self.audit.record(
            action="incident.alert_linked",
            actor=actor,
            target_type="incident",
            target_id=incident.id,
            detail=f"Linked alert {alert_id}",
            ip_address=ip_address,
        )

    def unlink_alert(self, incident: Incident, alert_id: str, actor: User, ip_address: str = "") -> None:
        link = self.repo.get_alert_link(incident.id, alert_id)
        if link is None:
            raise IncidentError("This alert is not linked to the incident.")
        self.repo.unlink_alert(link)
        self.audit.record(
            action="incident.alert_unlinked",
            actor=actor,
            target_type="incident",
            target_id=incident.id,
            detail=f"Unlinked alert {alert_id}",
            ip_address=ip_address,
        )

    def link_asset(self, incident: Incident, asset_id: str, actor: User, ip_address: str = "") -> None:
        if self.db.get(Asset, asset_id) is None:
            raise IncidentError(f"Asset '{asset_id}' does not exist.")
        if self.repo.get_asset_link(incident.id, asset_id) is not None:
            raise IncidentError("This asset is already linked to the incident.")

        self.repo.link_asset(incident.id, asset_id, datetime.now(timezone.utc))
        self.audit.record(
            action="incident.asset_linked",
            actor=actor,
            target_type="incident",
            target_id=incident.id,
            detail=f"Linked asset {asset_id}",
            ip_address=ip_address,
        )

    # --- Status / assignment / resolution ---

    def update(
        self,
        incident: Incident,
        *,
        title: str | None = None,
        description: str | None = None,
        status: IncidentStatus | None = None,
        assigned_to: str | None = None,
        resolution: str | None = None,
        actor: User,
        ip_address: str = "",
    ) -> Incident:
        updates: dict = {}
        if title is not None and title != incident.title:
            updates["title"] = title
        if description is not None and description != incident.description:
            updates["description"] = description
        if status is not None and status != incident.status:
            updates["status"] = status
        if assigned_to is not None and assigned_to != incident.assigned_to:
            updates["assigned_to"] = assigned_to
        if resolution is not None and resolution != incident.resolution:
            updates["resolution"] = resolution

        if not updates:
            return incident

        updated = self.repo.update(incident, **updates)
        self.audit.record(
            action="incident.updated",
            actor=actor,
            target_type="incident",
            target_id=incident.id,
            detail=", ".join(f"{k}={v}" for k, v in updates.items()),
            ip_address=ip_address,
        )
        return updated

    # --- Notes ---

    def add_note(self, incident: Incident, content: str, actor: User) -> InvestigationNote:
        note = self.repo.add_note(
            incident_id=incident.id,
            author_user_id=actor.id,
            author_username=actor.username,
            content=content,
        )
        self.audit.record(
            action="incident.note_added",
            actor=actor,
            target_type="incident",
            target_id=incident.id,
            detail=f"Note added ({len(content)} chars)",
        )
        return note

    # --- Timeline ---

    def get_timeline(self, incident: Incident) -> list[TimelineEntry]:
        entries: list[TimelineEntry] = []

        alert_links = self.repo.list_alert_links(incident.id)
        event_ids: set[str] = set()
        for link in alert_links:
            alert = self.db.get(Alert, link.alert_id)
            if alert is None:
                continue
            try:
                event_ids.update(json.loads(alert.evidence or "[]"))
            except (json.JSONDecodeError, TypeError):
                continue

        if event_ids:
            events = self.db.query(NetworkEvent).filter(NetworkEvent.id.in_(event_ids)).all()
            for event in events:
                entries.append(
                    TimelineEntry(
                        timestamp=event.timestamp,
                        kind="event",
                        summary=f"{event.event_type}: {event.description}",
                        detail=f"source={event.event_source.value}, confidence={event.confidence:.0%}",
                    )
                )

        for note in self.repo.list_notes(incident.id):
            entries.append(
                TimelineEntry(
                    timestamp=note.created_at,
                    kind="note",
                    summary=f"Note by {note.author_username}",
                    detail=note.content,
                )
            )

        audit_entries = (
            self.db.query(AuditLog)
            .filter(AuditLog.target_type == "incident", AuditLog.target_id == incident.id)
            .all()
        )
        for entry in audit_entries:
            entries.append(
                TimelineEntry(
                    timestamp=entry.created_at,
                    kind="audit",
                    summary=f"{entry.action} by {entry.actor_username}",
                    detail=entry.detail,
                )
            )

        entries.sort(key=lambda e: e.timestamp)
        return entries
