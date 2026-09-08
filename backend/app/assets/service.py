"""
Asset application service.

`upsert_from_discovery` is the one place discovery results turn into
Asset rows, AssetHistory entries, and NetworkEvents. It is intentionally
conservative: it never marks an asset "malicious" — a newly seen asset
is `trust_status=UNKNOWN`, not untrusted. An analyst decides trust.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from ipaddress import ip_address

from sqlalchemy.orm import Session

from app.assets.models import Asset, AssetChangeType, AssetCriticality, AssetStatus, AssetTrustStatus
from app.assets.repository import AssetRepository
from app.events.models import EventSeverity, EventSource, NetworkEvent


@dataclass
class DiscoveredHost:
    """Normalized shape a DiscoveryCollector returns — decoupled from any
    specific collector's (e.g. Nmap's) native output format."""

    ip_address: str
    mac_address: str | None = None
    hostname: str | None = None
    operating_system: str | None = None
    vendor: str | None = None
    open_ports: list[int] | None = None


@dataclass
class UpsertResult:
    asset: Asset
    is_new: bool
    changes: list[AssetChangeType]


class AssetService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AssetRepository(db)

    # --- Discovery ingestion ---

    def upsert_from_discovery(self, host: DiscoveredHost, *, source: str = "discovery") -> UpsertResult:
        host = self._normalize_host(host)
        now = datetime.now(timezone.utc)

        # Prefer MAC as the stable identity key (IP can rotate via DHCP);
        # fall back to IP if MAC wasn't observable.
        existing = self.repo.get_by_mac(host.mac_address) if host.mac_address else None
        if existing is None:
            existing = self.repo.get_by_ip(host.ip_address)

        if existing is None:
            asset = self.repo.create(
                ip_address=host.ip_address,
                mac_address=host.mac_address,
                hostname=host.hostname,
                operating_system=host.operating_system,
                vendor=host.vendor,
                status=AssetStatus.ONLINE,
                trust_status=AssetTrustStatus.UNKNOWN,
                criticality=AssetCriticality.LOW,
                first_seen=now,
                last_seen=now,
            )
            self.repo.add_history(
                asset_id=asset.id,
                change_type=AssetChangeType.FIRST_DISCOVERED,
                previous_value="",
                new_value=host.ip_address,
                source=source,
                changed_at=now,
            )
            self._write_event(
                event_type="NEW_DEVICE",
                asset_id=asset.id,
                severity=EventSeverity.MEDIUM,
                description=f"Previously unknown device detected at {host.ip_address}.",
                evidence=[{"observed_ip": host.ip_address, "observed_mac": host.mac_address}],
                source=source,
            )
            return UpsertResult(asset=asset, is_new=True, changes=[AssetChangeType.FIRST_DISCOVERED])

        changes: list[AssetChangeType] = []

        if host.ip_address and existing.ip_address != host.ip_address:
            self.repo.add_history(
                asset_id=existing.id,
                change_type=AssetChangeType.IP_CHANGED,
                previous_value=existing.ip_address or "",
                new_value=host.ip_address,
                source=source,
                changed_at=now,
            )
            self._write_event(
                event_type="IP_CHANGED",
                asset_id=existing.id,
                severity=EventSeverity.LOW,
                description=f"Asset IP changed from {existing.ip_address} to {host.ip_address}.",
                evidence=[{"previous_ip": existing.ip_address, "new_ip": host.ip_address}],
                source=source,
            )
            changes.append(AssetChangeType.IP_CHANGED)

        if host.mac_address and existing.mac_address and existing.mac_address != host.mac_address:
            self.repo.add_history(
                asset_id=existing.id,
                change_type=AssetChangeType.MAC_CHANGED,
                previous_value=existing.mac_address,
                new_value=host.mac_address,
                source=source,
                changed_at=now,
            )
            self._write_event(
                event_type="MAC_CHANGED",
                asset_id=existing.id,
                severity=EventSeverity.MEDIUM,  # a device presenting a new MAC on the same identity is notable
                description=f"Asset MAC changed from {existing.mac_address} to {host.mac_address}.",
                evidence=[{"previous_mac": existing.mac_address, "new_mac": host.mac_address}],
                source=source,
            )
            changes.append(AssetChangeType.MAC_CHANGED)

        if host.hostname and existing.hostname != host.hostname:
            self.repo.add_history(
                asset_id=existing.id,
                change_type=AssetChangeType.HOSTNAME_CHANGED,
                previous_value=existing.hostname or "",
                new_value=host.hostname,
                source=source,
                changed_at=now,
            )
            changes.append(AssetChangeType.HOSTNAME_CHANGED)

        if existing.status != AssetStatus.ONLINE:
            self.repo.add_history(
                asset_id=existing.id,
                change_type=AssetChangeType.STATUS_CHANGED,
                previous_value=existing.status.value,
                new_value=AssetStatus.ONLINE.value,
                source=source,
                changed_at=now,
            )
            changes.append(AssetChangeType.STATUS_CHANGED)

        updated = self.repo.update(
            existing,
            ip_address=host.ip_address or existing.ip_address,
            mac_address=host.mac_address or existing.mac_address,
            hostname=host.hostname or existing.hostname,
            operating_system=host.operating_system or existing.operating_system,
            vendor=host.vendor or existing.vendor,
            status=AssetStatus.ONLINE,
            last_seen=now,
        )

        return UpsertResult(asset=updated, is_new=False, changes=changes)

    @staticmethod
    def _normalize_host(host: DiscoveredHost) -> DiscoveredHost:
        """Normalize identifiers before identity matching and persistence."""
        normalized_ip = host.ip_address.strip()
        try:
            normalized_ip = ip_address(normalized_ip).compressed
        except ValueError:
            pass

        normalized_mac = host.mac_address.strip().lower().replace("-", ":") if host.mac_address else None
        normalized_hostname = host.hostname.strip().rstrip(".").lower() if host.hostname else None

        return DiscoveredHost(
            ip_address=normalized_ip,
            mac_address=normalized_mac,
            hostname=normalized_hostname,
            operating_system=host.operating_system.strip() if host.operating_system else None,
            vendor=host.vendor.strip() if host.vendor else None,
            open_ports=host.open_ports,
        )

    # --- Analyst-facing operations ---

    def update_metadata(
        self,
        asset: Asset,
        *,
        device_type: str | None = None,
        owner: str | None = None,
        criticality: AssetCriticality | None = None,
        trust_status: AssetTrustStatus | None = None,
    ) -> Asset:
        now = datetime.now(timezone.utc)
        updates: dict = {}

        if device_type is not None and device_type != asset.device_type:
            updates["device_type"] = device_type
        if owner is not None and owner != asset.owner:
            updates["owner"] = owner
        if criticality is not None and criticality != asset.criticality:
            updates["criticality"] = criticality
        if trust_status is not None and trust_status != asset.trust_status:
            updates["trust_status"] = trust_status

        if not updates:
            return asset

        self.repo.add_history(
            asset_id=asset.id,
            change_type=AssetChangeType.METADATA_CHANGED,
            previous_value=json.dumps({k: getattr(asset, k).value if hasattr(getattr(asset, k), "value") else getattr(asset, k) for k in updates}),
            new_value=json.dumps({k: (v.value if hasattr(v, "value") else v) for k, v in updates.items()}),
            source="manual",
            changed_at=now,
        )

        return self.repo.update(asset, **updates)

    # --- internal ---

    def _write_event(
        self,
        *,
        event_type: str,
        asset_id: str,
        severity: EventSeverity,
        description: str,
        evidence: list[dict],
        source: str,
    ) -> NetworkEvent:
        event = NetworkEvent(
            event_type=event_type,
            event_source=EventSource.DISCOVERY if source == "discovery" else EventSource.MANUAL,
            timestamp=datetime.now(timezone.utc),
            asset_id=asset_id,
            severity=severity,
            confidence=1.0,  # discovery observations are directly measured, not inferred
            description=description,
            evidence=json.dumps(evidence),
            is_synthetic=False,
        )
        self.db.add(event)
        self.db.commit()
        return event
