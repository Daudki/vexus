from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.monitoring.models import MetricType


class MonitoringSampleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    metric_type: MetricType
    value: float
    timestamp: datetime
    is_synthetic: bool


class PollSummaryRead(BaseModel):
    assets_checked: int
    went_offline: int
    went_online: int
    missing_flagged: int


class NetworkHealthOverview(BaseModel):
    online: int
    offline: int
    unknown: int
    average_latency_ms: float | None
    data_quality_warnings: list[str]
