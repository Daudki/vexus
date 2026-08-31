"""
Discovery application service.

Orchestration only: validate scope -> run collector -> upsert assets ->
record the scan job -> update the discovery worker heartbeat (VEXUS
Health) -> audit log. All of the actual "what changed" logic lives in
AssetService; all of the "is this allowed" logic lives in scope.py.
"""
import json
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network

from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetChangeType, AssetStatus, AssetHistory
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
            self._mark_missing_assets_in_scan(hosts, target_ranges, now)

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

    def _mark_missing_assets_in_scan(self, hosts: list, target_ranges: list[str], now: datetime) -> None:
        observed_ips = {host.ip_address for host in hosts if getattr(host, "ip_address", None)}
        networks = [ip_network(range_value, strict=False) for range_value in target_ranges]

        assets = self.db.query(Asset).filter(Asset.ip_address.isnot(None)).all()
        for asset in assets:
            if not asset.ip_address:
                continue
            try:
                asset_ip = ip_address(asset.ip_address)
            except ValueError:
                continue

            in_current_scope = any(asset_ip in network for network in networks)

            if asset.ip_address in observed_ips:
                if asset.status != AssetStatus.ONLINE:
                    self.db.add(
                        self._status_history_entry(asset, AssetStatus.ONLINE, now, source="discovery")
                    )
                    asset.status = AssetStatus.ONLINE
                asset.last_seen = now
                self.db.commit()
                continue

            if not in_current_scope:
                if asset.status == AssetStatus.OFFLINE:
                    continue
                self.db.add(
                    self._status_history_entry(asset, AssetStatus.OFFLINE, now, source="discovery")
                )
                asset.status = AssetStatus.OFFLINE
                asset.last_seen = now
                self.db.commit()
                continue

            if asset.status == AssetStatus.OFFLINE:
                continue

            self.db.add(
                self._status_history_entry(asset, AssetStatus.OFFLINE, now, source="discovery")
            )
            asset.status = AssetStatus.OFFLINE
            asset.last_seen = now
            self.db.commit()

    def _status_history_entry(self, asset: Asset, status: AssetStatus, now: datetime, *, source: str):
        return AssetHistory(
            asset_id=asset.id,
            change_type=AssetChangeType.STATUS_CHANGED,
            previous_value=asset.status.value,
            new_value=status.value,
            source=source,
            changed_at=now,
        )

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
