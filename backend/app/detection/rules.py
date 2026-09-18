"""
Detection rules.

Each rule is a small, independent class that consumes NetworkEvents of
one event_type and produces Findings — structured, evidence-linked
candidates for an Alert. Rules never invent severity/confidence out of
thin air: severity defaults to what the source event already carries
(it was set by Discover/Watch based on direct observation), and a rule
only overrides it when it's adding real security judgment beyond the
raw event (see MacChangeRule).

Only 5 rules are implemented, deliberately. The original design also
called for port-exposure, connection-failure, authentication-pattern,
and traffic-volume rules — none of those have a real data source in
VEXUS yet (no port history, no auth/connection logs, no traffic volume
metric), and fabricating detections from data that doesn't exist would
violate Evidence First. They're listed as NOT_IMPLEMENTED_RULES at the
bottom of this file so it's clear what's missing and why, rather than
silently absent.
"""
from dataclasses import dataclass, field
from typing import Protocol

from app.events.models import EventSeverity, NetworkEvent


@dataclass
class Finding:
    rule_key: str
    asset_id: str
    severity: EventSeverity
    confidence: float
    description: str
    source_event_ids: list[str] = field(default_factory=list)
    # Set by DetectionEngine.run() after evaluate() returns, based on
    # whether every contributing event is synthetic -- individual rules
    # don't need to know about Simulation Mode themselves.
    is_synthetic: bool = False


class DetectionRule(Protocol):
    rule_key: str
    event_type: str  # the single NetworkEvent.event_type this rule consumes

    def evaluate(self, events: list[NetworkEvent]) -> list[Finding]: ...


class NewDeviceRule:
    rule_key = "new_device_detection"
    event_type = "NEW_DEVICE"

    def evaluate(self, events: list[NetworkEvent]) -> list[Finding]:
        return [
            Finding(
                rule_key=self.rule_key,
                asset_id=e.asset_id,
                severity=e.severity,
                confidence=e.confidence,
                description=e.description,
                source_event_ids=[e.id],
            )
            for e in events
            if e.event_type == self.event_type and e.asset_id
        ]


class IpChangeRule:
    rule_key = "ip_change_detection"
    event_type = "IP_CHANGED"

    def evaluate(self, events: list[NetworkEvent]) -> list[Finding]:
        return [
            Finding(
                rule_key=self.rule_key,
                asset_id=e.asset_id,
                severity=e.severity,
                confidence=e.confidence,
                description=e.description,
                source_event_ids=[e.id],
            )
            for e in events
            if e.event_type == self.event_type and e.asset_id
        ]


class MacChangeRule:
    rule_key = "mac_change_detection"
    event_type = "MAC_CHANGED"

    def evaluate(self, events: list[NetworkEvent]) -> list[Finding]:
        findings = []
        for e in events:
            if e.event_type != self.event_type or not e.asset_id:
                continue
            findings.append(
                Finding(
                    rule_key=self.rule_key,
                    asset_id=e.asset_id,
                    # Overridden to HIGH regardless of the event's own severity:
                    # a device presenting a new MAC on an identity VEXUS already
                    # knows is a stronger signal (possible spoofing/hardware
                    # swap) than the raw event alone conveys. This is the
                    # detection engine adding judgment, not just relaying data.
                    severity=EventSeverity.HIGH,
                    confidence=e.confidence,
                    description=e.description,
                    source_event_ids=[e.id],
                )
            )
        return findings


class AvailabilityAnomalyRule:
    rule_key = "availability_anomaly_detection"
    event_type = "AVAILABILITY_ANOMALY"

    def evaluate(self, events: list[NetworkEvent]) -> list[Finding]:
        return [
            Finding(
                rule_key=self.rule_key,
                asset_id=e.asset_id,
                severity=e.severity,
                confidence=e.confidence,
                description=e.description,
                source_event_ids=[e.id],
            )
            for e in events
            if e.event_type == self.event_type and e.asset_id
        ]


class AssetMissingRule:
    rule_key = "asset_missing_detection"
    event_type = "ASSET_MISSING"

    def evaluate(self, events: list[NetworkEvent]) -> list[Finding]:
        return [
            Finding(
                rule_key=self.rule_key,
                asset_id=e.asset_id,
                severity=e.severity,
                confidence=e.confidence,
                description=e.description,
                source_event_ids=[e.id],
            )
            for e in events
            if e.event_type == self.event_type and e.asset_id
        ]


DEFAULT_RULES: list[DetectionRule] = [
    NewDeviceRule(),
    IpChangeRule(),
    MacChangeRule(),
    AvailabilityAnomalyRule(),
    AssetMissingRule(),
]

# Listed from the original design but not implemented — no real data
# source exists in VEXUS for any of these yet:
#   - unexpected_service_exposure / unusual_port_exposure: needs a
#     baseline of "expected" ports (VEXUS Sense) or an explicit
#     allowlist config; neither exists.
#   - repeated_connection_failure / suspicious_authentication_pattern:
#     needs auth/connection log ingestion; VEXUS has no log source.
#   - traffic_volume_anomaly: needs a traffic volume metric; Watch only
#     collects latency/packet-loss/availability.
NOT_IMPLEMENTED_RULES = [
    "unexpected_service_exposure",
    "unusual_port_exposure",
    "repeated_connection_failure",
    "suspicious_authentication_pattern",
    "traffic_volume_anomaly",
]
