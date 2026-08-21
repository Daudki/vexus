from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.alerts.models import Alert, AlertStatus

_CLOSED_STATUSES = (AlertStatus.RESOLVED, AlertStatus.CLOSED, AlertStatus.FALSE_POSITIVE)


class AlertRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, alert_id: str) -> Alert | None:
        return self.db.get(Alert, alert_id)

    def find_active_by_dedup_key(self, dedup_key: str) -> Alert | None:
        """The most recent non-closed alert for this dedup key, if any —
        used to decide whether a new Finding should be merged into an
        existing alert or start a fresh one."""
        query = (
            select(Alert)
            .where(Alert.dedup_key == dedup_key, Alert.status.notin_(_CLOSED_STATUSES))
            .order_by(desc(Alert.last_seen))
        )
        return self.db.scalar(query)

    def list_alerts(
        self,
        *,
        status: AlertStatus | None = None,
        severity: str | None = None,
        asset_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Alert]:
        query = select(Alert)
        if status:
            query = query.where(Alert.status == status)
        if severity:
            query = query.where(Alert.severity == severity)
        if asset_id:
            query = query.where(Alert.asset_id == asset_id)
        query = query.order_by(desc(Alert.last_seen)).limit(limit).offset(offset)
        return list(self.db.scalars(query))

    def create(self, **kwargs) -> Alert:
        alert = Alert(**kwargs)
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def update(self, alert: Alert, **kwargs) -> Alert:
        for key, value in kwargs.items():
            setattr(alert, key, value)
        self.db.commit()
        self.db.refresh(alert)
        return alert
