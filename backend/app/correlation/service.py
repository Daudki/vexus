from sqlalchemy import select
from sqlalchemy.orm import Session

from app.alerts.models import Alert, AlertStatus
from app.correlation.domain import CorrelationCandidate, correlate_alerts

_CLOSED_STATUSES = (AlertStatus.RESOLVED, AlertStatus.CLOSED, AlertStatus.FALSE_POSITIVE)


class CorrelationService:
    def __init__(self, db: Session):
        self.db = db

    def find_candidates(self, *, window_seconds: int = 900) -> list[CorrelationCandidate]:
        alerts = list(
            self.db.scalars(
                select(Alert)
                .where(Alert.status.notin_(_CLOSED_STATUSES), Alert.suppressed.is_(False))
                .order_by(Alert.last_seen, Alert.id)
            )
        )
        return correlate_alerts(alerts, window_seconds=window_seconds)
