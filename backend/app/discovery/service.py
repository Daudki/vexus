"""
Discovery application service.

Orchestration only: validate scope -> run collector -> upsert assets ->
record the scan job -> update the discovery worker heartbeat (VEXUS
Health) -> audit log. All of the actual "what changed" logic lives in
AssetService; all of the "is this allowed" logic lives in scope.py.
"""
import json
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.assets.service import AssetService
from app.audit.service import AuditService
from app.discovery.collectors import DiscoveryCollector
from app.discovery.models import ScanJob, ScanStatus
from app.discovery.scope import ScopeError, validate_target_ranges
from app.health.models import WorkerHeartbeat
from app.users.models import User


class DiscoveryService:
    def __init__(self, db: Session, collector: DiscoveryCollector):
        self.db = db
        self.collector = collector
        self.assets = AssetService(db)
        self.audit = AuditService(db)

    def run_scan(self, target_ranges: list[str], initiated_by: User, ip_address: str = "") -> ScanJob:
        now = datetime.now(timezone.utc)

        try:
            validate_target_ranges(target_ranges)
        except ScopeError as exc:
            job = ScanJob(
                initiated_by_user_id=initiated_by.id,
                target_ranges=json.dumps(target_ranges),
                status=ScanStatus.REFUSED,
                started_at=now,
                completed_at=now,
                error_message=str(exc),
            )
            self.db.add(job)
            self.db.commit()
            self.db.refresh(job)

            self.audit.record(
                action="discovery.scan_refused",
                actor=initiated_by,
                target_type="scan_job",
                target_id=job.id,
                detail=str(exc),
                ip_address=ip_address,
                success=False,
            )
            return job

        job = ScanJob(
            initiated_by_user_id=initiated_by.id,
            target_ranges=json.dumps(target_ranges),
            status=ScanStatus.RUNNING,
            started_at=now,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        self.audit.record(
            action="discovery.scan_started",
            actor=initiated_by,
            target_type="scan_job",
            target_id=job.id,
            detail=f"Targets: {', '.join(target_ranges)}",
            ip_address=ip_address,
        )

        try:
            hosts = self.collector.discover(target_ranges)

            new_count = 0
            changed_count = 0
            for host in hosts:
                result = self.assets.upsert_from_discovery(host, source="discovery")
                if result.is_new:
                    new_count += 1
                elif result.changes:
                    changed_count += 1

            job.status = ScanStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            job.hosts_discovered = len(hosts)
            job.new_assets = new_count
            job.changed_assets = changed_count
            self.db.commit()
            self.db.refresh(job)

            self._update_heartbeat(status="ok", detail=f"{len(hosts)} hosts discovered")

            self.audit.record(
                action="discovery.scan_completed",
                actor=initiated_by,
                target_type="scan_job",
                target_id=job.id,
                detail=f"{len(hosts)} hosts, {new_count} new, {changed_count} changed",
                ip_address=ip_address,
            )

        except Exception as exc:  # noqa: BLE001 — never hide scan failures (Rule 4)
            job.status = ScanStatus.FAILED
            job.completed_at = datetime.now(timezone.utc)
            job.error_message = str(exc)
            self.db.commit()
            self.db.refresh(job)

            self._update_heartbeat(status="degraded", detail=str(exc))

            self.audit.record(
                action="discovery.scan_failed",
                actor=initiated_by,
                target_type="scan_job",
                target_id=job.id,
                detail=str(exc),
                ip_address=ip_address,
                success=False,
            )

        return job

    def _update_heartbeat(self, *, status: str, detail: str) -> None:
        hb = self.db.query(WorkerHeartbeat).filter_by(worker_name="discovery").first()
        now = datetime.now(timezone.utc)
        if hb is None:
            hb = WorkerHeartbeat(worker_name="discovery")
            self.db.add(hb)
        hb.last_success_at = now if status == "ok" else hb.last_success_at
        hb.status = status
        hb.detail = detail
        self.db.commit()
