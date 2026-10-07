from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import AuditService
from app.events.models import EventSeverity, EventSource, NetworkEvent
from app.threat_intel.provider import NVDProvider, ThreatIntelProviderError
from app.threat_intel.models import AssetVulnerability, Vulnerability, VulnerabilityMatchConfidence
from app.threat_intel.repository import AssetVulnerabilityRepository, VulnerabilityRepository
from app.assets.models import Asset, AssetNetworkService
from app.assets.repository import AssetRepository
from app.threat_intel.matching import cve_affects_service, parse_cpe
from app.threat_intel.schemas import AssetVulnerabilityRead, VulnerabilityRead
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
        if created or updated:
            AssetVulnerabilityService(self.db).match_cve(vulnerability)
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



AUTO_MATCH_SOURCE = "cpe_match"


@dataclass
class MatchSummary:
    assets_evaluated: int = 0
    links_created: int = 0
    links_removed: int = 0

    def add(self, other: "MatchSummary") -> None:
        self.assets_evaluated += other.assets_evaluated
        self.links_created += other.links_created
        self.links_removed += other.links_removed


class AssetVulnerabilityError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class AssetVulnerabilityService:
    def __init__(self, db: Session):
        self.db = db
        self.assets = AssetRepository(db)
        self.vulns = VulnerabilityRepository(db)
        self.links = AssetVulnerabilityRepository(db)
        self.audit = AuditService(db)

    @staticmethod
    def to_read(link, vulnerability) -> AssetVulnerabilityRead:
        return AssetVulnerabilityRead(
            id=link.id,
            asset_id=link.asset_id,
            cve_id=vulnerability.cve_id,
            cvss_score=vulnerability.cvss_score,
            cvss_severity=vulnerability.cvss_severity,
            is_rejected=vulnerability.is_rejected,
            confidence=link.confidence,
            match_source=link.match_source,
            created_at=link.created_at,
        )

    def _resolve(self, asset_id: str, cve_id: str):
        asset = self.assets.get_by_id(asset_id)
        if asset is None:
            raise AssetVulnerabilityError("Asset not found.", 404)
        vulnerability = self.vulns.get_by_cve(cve_id)
        if vulnerability is None:
            raise AssetVulnerabilityError("Vulnerability not found. Sync the CVE first.", 404)
        return asset, vulnerability

    def list_for_asset(self, asset_id: str) -> list[AssetVulnerabilityRead]:
        if self.assets.get_by_id(asset_id) is None:
            raise AssetVulnerabilityError("Asset not found.", 404)
        return [self.to_read(link, vuln) for link, vuln in self.links.list_for_asset(asset_id)]

    def link_manual(self, asset_id: str, cve_id: str, actor: User, ip_address: str = "") -> AssetVulnerabilityRead:
        asset, vulnerability = self._resolve(asset_id, cve_id)
        if vulnerability.is_rejected:
            raise AssetVulnerabilityError("This CVE has been rejected and cannot be linked to an asset.", 409)
        if self.links.get(asset.id, vulnerability.id) is not None:
            raise AssetVulnerabilityError("This CVE is already linked to the asset.", 409)

        link = self.links.create(
            AssetVulnerability(
                asset_id=asset.id,
                vulnerability_id=vulnerability.id,
                confidence=VulnerabilityMatchConfidence.CONFIRMED,
                match_source="manual",
                created_by_user_id=actor.id,
                is_synthetic=asset.is_synthetic,
            )
        )
        self.db.commit()
        self.db.refresh(link)
        self.audit.record(
            action="threat_intel.asset_vulnerability_linked",
            actor=actor,
            target_type="asset",
            target_id=asset.id,
            detail=f"Linked {vulnerability.cve_id} to asset (confirmed, manual).",
            ip_address=ip_address,
        )
        return self.to_read(link, vulnerability)

    def unlink(self, asset_id: str, cve_id: str, actor: User, ip_address: str = "") -> None:
        asset, vulnerability = self._resolve(asset_id, cve_id)
        link = self.links.get(asset.id, vulnerability.id)
        if link is None:
            raise AssetVulnerabilityError("This CVE is not linked to the asset.", 404)
        self.links.delete(link)
        self.db.commit()
        self.audit.record(
            action="threat_intel.asset_vulnerability_unlinked",
            actor=actor,
            target_type="asset",
            target_id=asset.id,
            detail=f"Unlinked {vulnerability.cve_id} from asset.",
            ip_address=ip_address,
        )


    def _candidates(self, vendor: str, product: str) -> list[Vulnerability]:
        marker = f":{vendor}:{product}:"
        query = select(Vulnerability).where(
            Vulnerability.is_rejected.is_(False),
            Vulnerability.affected_cpes.contains(marker, autoescape=True),
        )
        return list(self.db.scalars(query))

    def match_asset(self, asset: Asset) -> MatchSummary:
        services = list(
            self.db.scalars(
                select(AssetNetworkService).where(
                    AssetNetworkService.asset_id == asset.id, AssetNetworkService.cpe.is_not(None)
                )
            )
        )
        desired: set[str] = set()
        for svc in services:
            parsed = parse_cpe(svc.cpe)
            if parsed is None:
                continue
            for vuln in self._candidates(parsed.vendor, parsed.product):
                if cve_affects_service(vuln.raw_data, parsed):
                    desired.add(vuln.id)

        existing = {
            link.vulnerability_id: link
            for link in self.db.scalars(select(AssetVulnerability).where(AssetVulnerability.asset_id == asset.id))
        }
        summary = MatchSummary(assets_evaluated=1)
        for vuln_id, link in existing.items():
            if link.match_source == AUTO_MATCH_SOURCE and vuln_id not in desired:
                self.db.delete(link)
                summary.links_removed += 1
        for vuln_id in desired:
            if vuln_id in existing:
                continue
            self.db.add(
                AssetVulnerability(
                    asset_id=asset.id,
                    vulnerability_id=vuln_id,
                    confidence=VulnerabilityMatchConfidence.INFERRED,
                    match_source=AUTO_MATCH_SOURCE,
                    created_by_user_id=None,
                    is_synthetic=asset.is_synthetic,
                )
            )
            summary.links_created += 1
        self.db.commit()
        if summary.links_created or summary.links_removed:
            self.audit.record(
                action="threat_intel.auto_match",
                actor=None,
                target_type="asset",
                target_id=asset.id,
                detail=f"CPE match: {summary.links_created} linked, {summary.links_removed} removed.",
            )
        return summary

    def match_cve(self, vulnerability: Vulnerability) -> MatchSummary:
        summary = MatchSummary()
        try:
            affected = {(c.vendor, c.product) for c in map(parse_cpe, json.loads(vulnerability.affected_cpes)) if c}
        except json.JSONDecodeError:
            return summary
        asset_ids: set[str] = set()
        for vendor, product in affected:
            rows = self.db.scalars(
                select(AssetNetworkService.asset_id).where(
                    AssetNetworkService.cpe.contains(f":{vendor}:{product}:", autoescape=True)
                )
            )
            asset_ids.update(rows)
        for asset_id in asset_ids:
            asset = self.assets.get_by_id(asset_id)
            if asset is not None:
                summary.add(self.match_asset(asset))
        return summary

    def match_all(self, actor: User | None = None, ip_address: str = "") -> MatchSummary:
        summary = MatchSummary()
        asset_ids = set(
            self.db.scalars(select(AssetNetworkService.asset_id).where(AssetNetworkService.cpe.is_not(None)))
        )
        stale_ids = set(
            self.db.scalars(
                select(AssetVulnerability.asset_id).where(AssetVulnerability.match_source == AUTO_MATCH_SOURCE)
            )
        )
        for asset_id in asset_ids | stale_ids:
            asset = self.assets.get_by_id(asset_id)
            if asset is not None:
                summary.add(self.match_asset(asset))
        if actor is not None:
            self.audit.record(
                action="threat_intel.match_run",
                actor=actor,
                detail=(
                    f"Evaluated {summary.assets_evaluated} assets: "
                    f"{summary.links_created} linked, {summary.links_removed} removed."
                ),
                ip_address=ip_address,
            )
        return summary
