"""
Alert application service.

`upsert_from_finding` is the deduplication boundary described in the
architecture doc: a repeat of the same underlying detection (same rule
+ asset) within the rule's suppression window increments the existing
alert (`occurrence_count`, `last_seen`) instead of creating a new row.
Once occurrence_count reaches the rule's `alert_threshold`, the alert
is unsuppressed (surfaced to analysts) — below that, it's tracked but
marked `suppressed` so a single low-signal event doesn't page anyone.
"""
import json
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.alerts.models import Alert, AlertStatus
from app.alerts.repository import AlertRepository
from app.audit.service import AuditService
from app.detection.models import DetectionRuleConfig
from app.detection.rules import Finding
from app.users.models import User

MAX_EVIDENCE_EVENTS = 20  # bound evidence list size on long-lived, frequently-repeating alerts


class AlertService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AlertRepository(db)
        self.audit = AuditService(db)

    def upsert_from_finding(self, finding: Finding, config: DetectionRuleConfig) -> tuple[Alert, bool]:
        """Returns (alert, was_created).

        The dedup key includes whether the finding is synthetic so a
        simulated finding can never merge into (or extend the evidence
        trail of) a real alert for the same rule+asset, or vice versa —
        they get entirely separate alert records instead.
        """
        now = datetime.now(timezone.utc)
        dedup_key = f"{finding.rule_key}:{finding.asset_id}:{'sim' if finding.is_synthetic else 'real'}"

        existing = self.repo.find_active_by_dedup_key(dedup_key)
        window = timedelta(minutes=config.suppression_window_minutes)

        if existing is not None and (now - existing.last_seen.replace(tzinfo=timezone.utc)) <= window:
            evidence = json.loads(existing.evidence or "[]")
            evidence.extend(finding.source_event_ids)
            evidence = evidence[-MAX_EVIDENCE_EVENTS:]

            new_count = existing.occurrence_count + 1
            updated = self.repo.update(
                existing,
                occurrence_count=new_count,
                last_seen=now,
                evidence=json.dumps(evidence),
                suppressed=new_count < config.alert_threshold,
            )
            return updated, False

        alert = self.repo.create(
            rule_key=finding.rule_key,
            asset_id=finding.asset_id,
            severity=finding.severity,
            confidence=finding.confidence,
            status=AlertStatus.NEW,
            description=finding.description,
            evidence=json.dumps(finding.source_event_ids),
            dedup_key=dedup_key,
            occurrence_count=1,
            first_seen=now,
            last_seen=now,
            suppressed=config.alert_threshold > 1,
            is_synthetic=finding.is_synthetic,
        )
        return alert, True

    # --- Analyst-facing status management ---

    def update_status(
        self, alert: Alert, *, status: AlertStatus | None, assigned_to: str | None, actor: User, ip_address: str = ""
    ) -> Alert:
        updates: dict = {}
        if status is not None and status != alert.status:
            updates["status"] = status
        if assigned_to is not None and assigned_to != alert.assigned_to:
            updates["assigned_to"] = assigned_to

        if not updates:
            return alert

        updated = self.repo.update(alert, **updates)

        self.audit.record(
            action="alert.update",
            actor=actor,
            target_type="alert",
            target_id=alert.id,
            detail=", ".join(f"{k}={v}" for k, v in updates.items()),
            ip_address=ip_address,
        )
        return updated
