import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.alerts.models import AlertStatus
from app.events.models import EventSeverity


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_key: str
    asset_id: str | None
    severity: EventSeverity
    confidence: float
    status: AlertStatus
    description: str
    evidence: list[str]
    dedup_key: str
    occurrence_count: int
    first_seen: datetime
    last_seen: datetime
    suppressed: bool
    assigned_to: str | None
    is_synthetic: bool

    @field_validator("evidence", mode="before")
    @classmethod
    def _parse_evidence(cls, value):
        if isinstance(value, str):
            return json.loads(value)
        return value


class AlertUpdate(BaseModel):
    status: AlertStatus | None = None
    assigned_to: str | None = None
