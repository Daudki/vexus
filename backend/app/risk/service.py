"""
Risk application service — the scoring engine.

`compute_for_asset` is the only place a risk score is calculated, and
it always returns/persists the full factor breakdown alongside the
total — there is no code path that produces a bare number. Weights are
module-level constants (not hidden inline literals) specifically so
they're visible and can be pointed to when someone asks "why is this
device high risk" instead of having to read scoring logic to find out.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.alerts.models import Alert, AlertStatus
from app.assets.models import Asset, AssetCriticality, AssetTrustStatus
from app.audit.service import AuditService
from app.common.models import DataQualityWarning
from app.events.models import EventSeverity
from app.health.models import WorkerHeartbeat
from app.risk.models import RiskLevel, RiskScore
from app.risk.repository import RiskRepository
from app.users.models import User

# --- Weights (visible, documented, tunable by editing these constants) ---

CRITICALITY_WEIGHTS: dict[AssetCriticality, float] = {
    AssetCriticality.LOW: 0,
    AssetCriticality.MEDIUM: 8,
    AssetCriticality.HIGH: 16,
    AssetCriticality.CRITICAL: 25,
}

TRUST_WEIGHTS: dict[AssetTrustStatus, float] = {
    AssetTrustStatus.TRUSTED: 0,
    AssetTrustStatus.UNKNOWN: 10,
    AssetTrustStatus.UNTRUSTED: 25,
}

ALERT_SEVERITY_WEIGHTS: dict[EventSeverity, float] = {
    EventSeverity.INFORMATIONAL: 0,
    EventSeverity.LOW: 4,
    EventSeverity.MEDIUM: 8,
    EventSeverity.HIGH: 14,
    EventSeverity.CRITICAL: 20,
}
ALERT_CONTRIBUTION_CAP = 40  # one asset can't hit CRITICAL purely from alert volume

_ACTIVE_ALERT_STATUSES = (
    AlertStatus.NEW,
    AlertStatus.ACKNOWLEDGED,
    AlertStatus.INVESTIGATING,
)

# Score buckets — documented here since "why is this HIGH and not MEDIUM"
# should be answerable by reading this file, not guessing.
LEVEL_THRESHOLDS = [
    (70, RiskLevel.CRITICAL),
    (45, RiskLevel.HIGH),
    (20, RiskLevel.MEDIUM),
    (0, RiskLevel.LOW),
]

STALE_DETECTION_MINUTES = 15


def _level_for_score(score: float) -> RiskLevel:
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return RiskLevel.LOW


@dataclass
class RecomputeSummary:
    assets_scored: int
    average_score: float
    detection_data_stale: bool


class RiskEngine:
    def __init__(self, db: Session):
        self.db = db
        self.repo = RiskRepository(db)
        self.audit = AuditService(db)

    def compute_for_asset(self, asset: Asset) -> RiskScore:
        now = datetime.now(timezone.utc)
        factors: list[dict] = []

        crit_points = CRITICALITY_WEIGHTS[asset.criticality]
        factors.append(
            {
                "factor_key": "criticality",
                "label": f"Asset criticality: {asset.criticality.value}",
                "points": crit_points,
                "description": "Set by an analyst; higher-criticality assets carry more inherent risk.",
            }
        )

        trust_points = TRUST_WEIGHTS[asset.trust_status]
        factors.append(
            {
                "factor_key": "trust_status",
                "label": f"Trust status: {asset.trust_status.value}",
                "points": trust_points,
                "description": "Unknown assets are not assumed malicious, but do carry elevated uncertainty.",
            }
        )

        active_alerts = (
            self.db.query(Alert)
            .filter(Alert.asset_id == asset.id, Alert.status.in_(_ACTIVE_ALERT_STATUSES))
            .all()
        )
        alert_points_raw = sum(ALERT_SEVERITY_WEIGHTS[a.severity] * a.confidence for a in active_alerts)
        alert_points = min(alert_points_raw, ALERT_CONTRIBUTION_CAP)

        for alert in active_alerts:
            factors.append(
                {
                    "factor_key": "alert",
                    "label": f"Active alert: {alert.rule_key} ({alert.severity.value})",
                    "points": ALERT_SEVERITY_WEIGHTS[alert.severity] * alert.confidence,
                    "description": f"Confidence {alert.confidence:.0%}, {alert.occurrence_count} occurrence(s).",
                }
            )
        if alert_points_raw > ALERT_CONTRIBUTION_CAP:
            factors.append(
                {
                    "factor_key": "alert_cap",
                    "label": "Alert contribution capped",
                    "points": alert_points - alert_points_raw,  # negative — shows the reduction explicitly
                    "description": (
                        f"Raw alert contribution ({alert_points_raw:.1f}) exceeds the "
                        f"{ALERT_CONTRIBUTION_CAP}-point cap; capped so alert volume alone can't "
                        "drive an asset to CRITICAL."
                    ),
                }
            )

        total = max(0.0, min(100.0, crit_points + trust_points + alert_points))
        level = _level_for_score(total)

        risk_score = self.repo.create_score(
            asset_id=asset.id, score=total, risk_level=level, computed_at=now, is_synthetic=False
        )
        for factor in factors:
            self.repo.add_factor(risk_score_id=risk_score.id, **factor)

        asset.risk_score = total
        self.db.commit()

        return risk_score

    def _detection_data_is_stale(self) -> bool:
        hb = self.db.query(WorkerHeartbeat).filter_by(worker_name="detection").first()
        if hb is None or hb.last_success_at is None:
            return True
        age = datetime.now(timezone.utc) - hb.last_success_at.replace(tzinfo=timezone.utc)
        return age > timedelta(minutes=STALE_DETECTION_MINUTES)

    def recompute_all(self, actor: User | None = None, ip_address: str = "") -> RecomputeSummary:
        assets = self.db.query(Asset).all()
        stale = self._detection_data_is_stale()

        scores = [self.compute_for_asset(a).score for a in assets]
        average = sum(scores) / len(scores) if scores else 0.0

        if stale:
            self.db.add(
                DataQualityWarning(
                    subject_type="risk",
                    subject_id=None,
                    message=(
                        "Detection has not completed a run recently. Alert-derived risk factors may be "
                        "based on stale data."
                    ),
                )
            )
            self.db.commit()

        hb = self.db.query(WorkerHeartbeat).filter_by(worker_name="risk").first()
        now = datetime.now(timezone.utc)
        if hb is None:
            hb = WorkerHeartbeat(worker_name="risk")
            self.db.add(hb)
        hb.last_success_at = now
        hb.status = "ok"
        hb.detail = f"{len(assets)} assets scored"
        self.db.commit()

        if actor is not None:
            self.audit.record(
                action="risk.recompute_completed",
                actor=actor,
                detail=f"{len(assets)} assets scored, average score {average:.1f}",
                ip_address=ip_address,
            )

        return RecomputeSummary(assets_scored=len(assets), average_score=average, detection_data_stale=stale)
