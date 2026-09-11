from datetime import datetime

from pydantic import BaseModel

from app.events.models import EventSeverity


class CorrelationCandidateRead(BaseModel):
    alert_ids: list[str]
    asset_ids: list[str]
    severity: EventSeverity
    confidence: float
    started_at: datetime
    last_seen: datetime
    is_synthetic: bool
