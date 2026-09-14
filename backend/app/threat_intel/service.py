from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.threat_intel.provider import NVDProvider, ThreatIntelProviderError
from app.threat_intel.repository import VulnerabilityRepository
from app.threat_intel.schemas import VulnerabilityRead
from app.users.models import User


class ThreatIntelService:
    def __init__(self, db: Session, provider: NVDProvider):
        self.db = db
        self.provider = provider
        self.repo = VulnerabilityRepository(db)
        self.audit = AuditService(db)

    def sync_cve(self, cve_id: str, actor: User | None = None, ip_address: str = "") -> tuple[object, bool, bool, str | None]:
        record = self.provider.fetch_cve(cve_id)
        vulnerability, created, updated = self.repo.upsert(record)

        event_id: str | None = None
        if created or updated:
            severity = self._severity(record.cvss_severity)
            event = NetworkEvent(
                event_type="THREAT_INTEL_VULNERABILITY_UPDATED",
                event_source=EventSource.THREAT_INTEL,
                timestamp=record.last_modified_at or record.published_at or datetime.now(timezone.utc),
                severity=severity,
                confidence=1.0,
                description=f"{record.cve_id} updated by {record.source} threat intelligence.",
                evidence=json.dumps([record.cve_id, record.source]),
                event_metadata=json.dumps({
                    "cve_id": record.cve_id,
                    "cvss_score": record.cvss_score,
                    "cvss_severity": record.cvss_severity,
                    "source": record.source,
                }),
                is_synthetic=False,
                processed_by_detection=False,
            )
            self.db.add(event)
            self.db.flush()
            event_id = event.id

        self.db.commit()
        self.db.refresh(vulnerability)
        if actor is not None:
            self.audit.record(
                action="threat_intel.cve_sync",
                actor=actor,
                target_type="vulnerability",
                target_id=vulnerability.id,
                detail=f"Synced {vulnerability.cve_id} from {vulnerability.source}; created={created}, updated={updated}.",
                ip_address=ip_address,
            )
        return vulnerability, created, updated, event_id

    @staticmethod
    def _severity(value: str | None) -> EventSeverity:
        normalized = (value or "").lower()
        return {
            "critical": EventSeverity.CRITICAL,
            "high": EventSeverity.HIGH,
            "medium": EventSeverity.MEDIUM,
            "low": EventSeverity.LOW,
        }.get(normalized, EventSeverity.INFORMATIONAL)

    @staticmethod
    def to_read(vulnerability) -> VulnerabilityRead:
        return VulnerabilityRead(
            id=vulnerability.id,
            cve_id=vulnerability.cve_id,
            source=vulnerability.source,
            description=vulnerability.description,
            cvss_score=vulnerability.cvss_score,
            cvss_severity=vulnerability.cvss_severity,
            cvss_version=vulnerability.cvss_version,
            published_at=vulnerability.published_at,
            last_modified_at=vulnerability.last_modified_at,
            cwe_ids=json.loads(vulnerability.cwe_ids or "[]"),
            affected_cpes=json.loads(vulnerability.affected_cpes or "[]"),
            references=json.loads(vulnerability.references or "[]"),
            is_rejected=vulnerability.is_rejected,
        )
