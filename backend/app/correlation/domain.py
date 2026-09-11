from dataclasses import dataclass
from datetime import datetime

from app.alerts.models import Alert
from app.events.models import EventSeverity


@dataclass(frozen=True)
class CorrelationCandidate:
    alert_ids: list[str]
    asset_ids: list[str]
    severity: EventSeverity
    confidence: float
    started_at: datetime
    last_seen: datetime
    is_synthetic: bool


_SEVERITY_ORDER = [
    EventSeverity.INFORMATIONAL,
    EventSeverity.LOW,
    EventSeverity.MEDIUM,
    EventSeverity.HIGH,
    EventSeverity.CRITICAL,
]


def correlate_alerts(alerts: list[Alert], window_seconds: int = 900) -> list[CorrelationCandidate]:
    """Group active alerts on the same asset when they overlap in time."""
    if window_seconds < 1:
        raise ValueError("window_seconds must be positive")

    groups: dict[str, list[Alert]] = {}
    for alert in sorted(alerts, key=lambda item: (item.last_seen, item.id)):
        if alert.asset_id is not None:
            groups.setdefault(alert.asset_id, []).append(alert)

    candidates: list[CorrelationCandidate] = []
    for asset_id, asset_alerts in groups.items():
        current: list[Alert] = []
        group_last_seen: datetime | None = None
        for alert in asset_alerts:
            if group_last_seen is None or (alert.first_seen - group_last_seen).total_seconds() <= window_seconds:
                current.append(alert)
            else:
                if len(current) > 1:
                    candidates.append(_candidate(current, asset_id))
                current = [alert]
            group_last_seen = max(group_last_seen or alert.last_seen, alert.last_seen)
        if len(current) > 1:
            candidates.append(_candidate(current, asset_id))

    return sorted(candidates, key=lambda item: (item.last_seen, item.alert_ids[0]), reverse=True)


def _candidate(alerts: list[Alert], asset_id: str) -> CorrelationCandidate:
    ordered_alerts = sorted(alerts, key=lambda item: (item.last_seen, item.id))
    return CorrelationCandidate(
        alert_ids=[alert.id for alert in ordered_alerts],
        asset_ids=[asset_id],
        severity=max((alert.severity for alert in alerts), key=_SEVERITY_ORDER.index),
        confidence=sum(alert.confidence for alert in alerts) / len(alerts),
        started_at=min(alert.first_seen for alert in alerts),
        last_seen=max(alert.last_seen for alert in alerts),
        is_synthetic=any(alert.is_synthetic for alert in alerts),
    )
