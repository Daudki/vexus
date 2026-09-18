"""
Simulation Mode (docs/vexus-v2.md, domain 14).

"Simulation allows VEXUS to demonstrate features without requiring a
live network. Every simulated record must remain identifiable.
Simulation data must never be mixed silently with production data."

run_scenario() creates a small, self-contained demo: a couple of
synthetic assets on the RFC 5737 TEST-NET-2 documentation range
(198.51.100.0/24 -- reserved specifically for examples, guaranteed to
never collide with anything a real discovery scan could ever find),
a few synthetic NetworkEvents using real detection-rule event types
so DetectionEngine.run() genuinely produces alerts from them (not a
separate, parallel "fake alert" path -- the exact same pipeline real
data goes through), and an audit trail entry.

reset() deletes every is_synthetic=True row it's responsible for, in
dependency order, so a demo can be cleanly torn down without leaving
orphaned data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.alerts.models import Alert
from app.assets.models import Asset, AssetChangeType, AssetCriticality, AssetHistory, AssetStatus, AssetTrustStatus
from app.assets.repository import AssetRepository
from app.audit.service import AuditService
from app.detection.service import DetectionEngine
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.incidents.models import Incident, IncidentAlert, IncidentAsset, InvestigationNote
from app.users.models import User

# RFC 5737 TEST-NET-2 -- reserved for documentation/examples, never
# assignable to a real device. Using real-looking private ranges
# (10.x/192.168.x) risked a simulated asset's IP accidentally colliding
# with a genuinely discovered one.
_SIM_SUBNET = "198.51.100"


@dataclass
class ScenarioResult:
    assets_created: int
    events_created: int
    alerts_created: int
    alerts_updated: int


@dataclass
class ResetResult:
    incidents_deleted: int
    alerts_deleted: int
    events_deleted: int
    assets_deleted: int


@dataclass
class SimulationStatus:
    active: bool
    assets: int
    events: int
    alerts: int
    incidents: int


class SimulationService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.audit = AuditService(db)

    def status(self) -> SimulationStatus:
        assets = self.db.query(Asset).filter_by(is_synthetic=True).count()
        events = self.db.query(NetworkEvent).filter_by(is_synthetic=True).count()
        alerts = self.db.query(Alert).filter_by(is_synthetic=True).count()
        incidents = self.db.query(Incident).filter_by(is_synthetic=True).count()
        return SimulationStatus(
            active=bool(assets or events or alerts or incidents),
            assets=assets,
            events=events,
            alerts=alerts,
            incidents=incidents,
        )

    def run_scenario(self, actor: User | None, ip_address: str = "") -> ScenarioResult:
        now = datetime.now(timezone.utc)

        workstation = self.assets.create(
            ip_address=f"{_SIM_SUBNET}.10",
            hostname="SIM-workstation-01",
            device_type="workstation",
            operating_system="Windows 11",
            status=AssetStatus.ONLINE,
            criticality=AssetCriticality.MEDIUM,
            trust_status=AssetTrustStatus.UNKNOWN,
            first_seen=now,
            last_seen=now,
            is_synthetic=True,
        )
        server = self.assets.create(
            ip_address=f"{_SIM_SUBNET}.20",
            hostname="SIM-app-server-01",
            device_type="server",
            operating_system="Ubuntu 24.04",
            status=AssetStatus.ONLINE,
            criticality=AssetCriticality.HIGH,
            trust_status=AssetTrustStatus.TRUSTED,
            first_seen=now,
            last_seen=now,
            is_synthetic=True,
        )
        for asset in (workstation, server):
            self.assets.add_history(
                asset_id=asset.id,
                change_type=AssetChangeType.FIRST_DISCOVERED,
                new_value=f"Simulated asset '{asset.hostname}' created by Simulation Mode.",
                source="simulation",
                changed_at=now,
            )

        events = [
            NetworkEvent(
                event_type="NEW_DEVICE",
                event_source=EventSource.SIMULATION,
                timestamp=now,
                asset_id=workstation.id,
                severity=EventSeverity.MEDIUM,
                confidence=0.9,
                description="Simulated: previously-unseen device appeared on the network.",
                evidence="[]",
                event_metadata="{}",
                is_synthetic=True,
                processed_by_detection=False,
            ),
            NetworkEvent(
                event_type="AVAILABILITY_ANOMALY",
                event_source=EventSource.SIMULATION,
                timestamp=now,
                asset_id=server.id,
                severity=EventSeverity.HIGH,
                confidence=0.85,
                description="Simulated: unexpected availability gap outside normal baseline.",
                evidence="[]",
                event_metadata="{}",
                is_synthetic=True,
                processed_by_detection=False,
            ),
        ]
        self.db.add_all(events)
        self.db.commit()

        summary = DetectionEngine(self.db).run(actor=actor, ip_address=ip_address)

        self.audit.record(
            action="simulation.run_scenario",
            actor=actor,
            target_type="simulation",
            target_id="demo-scenario",
            detail=(
                f"Created {len(events)} simulated event(s) across 2 simulated assets; "
                f"detection produced {summary.alerts_created} alert(s)."
            ),
            ip_address=ip_address,
        )

        return ScenarioResult(
            assets_created=2,
            events_created=len(events),
            alerts_created=summary.alerts_created,
            alerts_updated=summary.alerts_updated,
        )

    def reset(self, actor: User | None, ip_address: str = "") -> ResetResult:
        """Delete every is_synthetic=True row, in dependency order.

        Scoped to exactly what run_scenario() itself can create
        (assets, events, alerts, and any incident an analyst built from
        those alerts). If something outside that -- a RiskScore, a
        MonitoringSample, a TopologyRelationship -- was separately
        created against a simulated asset, the final asset delete will
        raise IntegrityError; that's surfaced clearly rather than
        silently ignored or blindly cascaded into tables this service
        has no business deleting from.
        """
        synthetic_incident_ids = [i.id for i in self.db.query(Incident.id).filter_by(is_synthetic=True).all()]
        if synthetic_incident_ids:
            self.db.execute(delete(InvestigationNote).where(InvestigationNote.incident_id.in_(synthetic_incident_ids)))
            self.db.execute(delete(IncidentAlert).where(IncidentAlert.incident_id.in_(synthetic_incident_ids)))
            self.db.execute(delete(IncidentAsset).where(IncidentAsset.incident_id.in_(synthetic_incident_ids)))
        incidents_deleted = self.db.query(Incident).filter_by(is_synthetic=True).delete()

        alerts_deleted = self.db.query(Alert).filter_by(is_synthetic=True).delete()
        events_deleted = self.db.query(NetworkEvent).filter_by(is_synthetic=True).delete()

        synthetic_asset_ids = [a.id for a in self.db.query(Asset.id).filter_by(is_synthetic=True).all()]
        if synthetic_asset_ids:
            self.db.execute(delete(AssetHistory).where(AssetHistory.asset_id.in_(synthetic_asset_ids)))

        try:
            assets_deleted = self.db.query(Asset).filter_by(is_synthetic=True).delete()
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            raise SimulationResetError(
                "Could not delete all simulated assets: other records still reference them "
                "(e.g. risk scores, monitoring samples, or topology relationships created "
                "outside the simulation scenario itself)."
            ) from exc

        self.audit.record(
            action="simulation.reset",
            actor=actor,
            target_type="simulation",
            target_id="demo-scenario",
            detail=(
                f"Deleted {incidents_deleted} incident(s), {alerts_deleted} alert(s), "
                f"{events_deleted} event(s), {assets_deleted} asset(s)."
            ),
            ip_address=ip_address,
        )

        return ResetResult(
            incidents_deleted=incidents_deleted,
            alerts_deleted=alerts_deleted,
            events_deleted=events_deleted,
            assets_deleted=assets_deleted,
        )


class SimulationResetError(Exception):
    pass
