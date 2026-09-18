from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.events.models import EventSeverity
from app.incidents.models import IncidentStatus


class IncidentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    alert_ids: list[str] = []
    asset_ids: list[str] = []
    severity: EventSeverity | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    description: str
    severity: EventSeverity
    confidence: float
    status: IncidentStatus
    assigned_to: str | None
    resolution: str
    created_at: datetime
    updated_at: datetime
    is_synthetic: bool


class IncidentDetailRead(IncidentRead):
    alert_ids: list[str] = []
    asset_ids: list[str] = []


class IncidentUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    status: IncidentStatus | None = None
    assigned_to: str | None = None
    resolution: str | None = None


class LinkAlertRequest(BaseModel):
    alert_id: str


class LinkAssetRequest(BaseModel):
    asset_id: str


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4096)


class NoteRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    author_username: str
    content: str
    created_at: datetime


class TimelineEntryRead(BaseModel):
    timestamp: datetime
    kind: str
    summary: str
    detail: str
