"""
Detection application service.

`DetectionEngine.run` is one cycle: pull unprocessed NetworkEvents
matching a registered rule's event_type, evaluate enabled rules,
upsert Findings into Alerts (dedup/suppression lives in AlertService),
mark the events processed, and update the detection worker heartbeat.
Nothing here invents severity or confidence — that's entirely the
rules' job (rules.py), and rules only use what's on the source event.
"""
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.alerts.service import AlertService
from app.audit.service import AuditService
from app.detection.models import DetectionRuleConfig
from app.detection.repository import DetectionRuleConfigRepository
from app.detection.rules import DEFAULT_RULES, DetectionRule
from app.events.models import NetworkEvent
from app.health.models import WorkerHeartbeat
from app.users.models import User

# Sensible defaults for rules that have no stored config yet. An
# operator can retune any of these later without a redeploy — this is
# just what a fresh install starts with.
DEFAULT_RULE_SETTINGS: dict[str, dict] = {
    "new_device_detection": dict(display_name="New Device Detection", confidence_threshold=0.7, alert_threshold=1, suppression_window_minutes=1440),
    "ip_change_detection": dict(display_name="IP Change Detection", confidence_threshold=0.7, alert_threshold=1, suppression_window_minutes=60),
    "mac_change_detection": dict(display_name="MAC Change Detection", confidence_threshold=0.7, alert_threshold=1, suppression_window_minutes=60),
    "availability_anomaly_detection": dict(display_name="Availability Anomaly Detection", confidence_threshold=0.7, alert_threshold=1, suppression_window_minutes=30),
    "asset_missing_detection": dict(display_name="Asset Missing Detection", confidence_threshold=0.7, alert_threshold=1, suppression_window_minutes=1440),
}


@dataclass
class DetectionRunSummary:
    events_evaluated: int
    findings_produced: int
    alerts_created: int
    alerts_updated: int


class DetectionEngine:
    def __init__(self, db: Session, rules: list[DetectionRule] | None = None):
        self.db = db
        self.rules = rules if rules is not None else DEFAULT_RULES
        self.config_repo = DetectionRuleConfigRepository(db)
        self.alerts = AlertService(db)
        self.audit = AuditService(db)

    def get_or_create_config(self, rule_key: str) -> DetectionRuleConfig:
        config = self.config_repo.get_by_rule_key(rule_key)
        if config is not None:
            return config
        defaults = DEFAULT_RULE_SETTINGS.get(rule_key, {})
        return self.config_repo.create(rule_key=rule_key, **defaults)

    def run(self, actor: User | None = None, ip_address: str = "", batch_size: int = 500) -> DetectionRunSummary:
        event_types = [rule.event_type for rule in self.rules]
        events = (
            self.db.query(NetworkEvent)
            .filter(NetworkEvent.processed_by_detection.is_(False), NetworkEvent.event_type.in_(event_types))
            .limit(batch_size)
            .all()
        )

        findings_total = 0
        created_total = 0
        updated_total = 0

        for rule in self.rules:
            config = self.get_or_create_config(rule.rule_key)
            if not config.enabled:
                continue

            rule_events = [e for e in events if e.event_type == rule.event_type]
            findings = [f for f in rule.evaluate(rule_events) if f.confidence >= config.confidence_threshold]
            findings_total += len(findings)

            # A finding is only synthetic if every event that
            # contributed to it is synthetic -- a mix of real and
            # simulated evidence must never be silently reported as
            # either one (VEXUS v2 Development Rules / Simulation Mode:
            # "simulation data must never be mixed silently with
            # production data").
            events_by_id = {e.id: e for e in rule_events}
            for finding in findings:
                contributing = [events_by_id[eid] for eid in finding.source_event_ids if eid in events_by_id]
                finding.is_synthetic = bool(contributing) and all(e.is_synthetic for e in contributing)

            for finding in findings:
                _alert, was_created = self.alerts.upsert_from_finding(finding, config)
                if was_created:
                    created_total += 1
                else:
                    updated_total += 1

        now = datetime.now(timezone.utc)
        for event in events:
            event.processed_by_detection = True
        self.db.commit()

        self._update_heartbeat(status="ok", detail=f"{len(events)} events evaluated", when=now)

        if actor is not None:
            self.audit.record(
                action="detection.run_completed",
                actor=actor,
                detail=f"{len(events)} events, {findings_total} findings, {created_total} alerts created, {updated_total} updated",
                ip_address=ip_address,
            )

        return DetectionRunSummary(
            events_evaluated=len(events),
            findings_produced=findings_total,
            alerts_created=created_total,
            alerts_updated=updated_total,
        )

    def _update_heartbeat(self, *, status: str, detail: str, when: datetime) -> None:
        hb = self.db.query(WorkerHeartbeat).filter_by(worker_name="detection").first()
        if hb is None:
            hb = WorkerHeartbeat(worker_name="detection")
            self.db.add(hb)
        if status == "ok":
            hb.last_success_at = when
        hb.status = status
        hb.detail = detail
        self.db.commit()
