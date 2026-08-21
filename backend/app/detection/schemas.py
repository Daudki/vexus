from pydantic import BaseModel, ConfigDict, Field

from app.detection.rules import DEFAULT_RULES, NOT_IMPLEMENTED_RULES
from app.events.models import EventSeverity


class DetectionRuleConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rule_key: str
    display_name: str
    description: str
    enabled: bool
    severity: EventSeverity
    confidence_threshold: float
    alert_threshold: int
    suppression_window_minutes: int


class DetectionRuleConfigUpdate(BaseModel):
    enabled: bool | None = None
    severity: EventSeverity | None = None
    confidence_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    alert_threshold: int | None = Field(default=None, ge=1)
    suppression_window_minutes: int | None = Field(default=None, ge=1)


class DetectionRunSummaryRead(BaseModel):
    events_evaluated: int
    findings_produced: int
    alerts_created: int
    alerts_updated: int


class DetectionRuleCatalog(BaseModel):
    """What rules exist and what doesn't — surfaced via the API so the
    frontend (and anyone reading /docs) can see the honest picture
    without digging through source."""

    implemented: list[str] = [r.rule_key for r in DEFAULT_RULES]
    not_implemented: list[str] = NOT_IMPLEMENTED_RULES
