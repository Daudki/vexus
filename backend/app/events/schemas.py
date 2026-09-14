"""
Schemas for the external event-ingestion boundary.

This is the "SOURCE -> EVENT -> NORMALIZATION -> VALIDATION -> STORAGE"
half of the VEXUS Network Event Contract (docs/vexus-v2.md, domain 5) —
detection/correlation/incident are unaffected, since ingested events
become ordinary NetworkEvent rows and flow through the exact same
DetectionEngine.run() as discovery- and monitoring-sourced events.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from app.events.models import EventSeverity, EventSource

# External callers may only claim to be one of these sources. DISCOVERY
# and MONITORING are written exclusively by VEXUS's own collectors —
# allowing an external caller to claim either would let a syslog feed
# impersonate a first-party subsystem. SIMULATION is exclusively
# Simulation Mode's own writer (see app/events/models.py docstring).
# IDENTITY has no adapter built yet, so it isn't accepted either —
# accepting it now would let external callers write events under a
# source label nothing downstream is prepared to reason about.
ALLOWED_INGEST_SOURCES = {EventSource.SYSLOG, EventSource.THREAT_INTEL, EventSource.MANUAL}

# Matches the NetworkEvent.evidence / event_metadata column size
# (String(4096)) -- rejected explicitly at the boundary rather than
# silently truncated, since a silently truncated evidence blob is
# corrupted evidence.
MAX_JSON_FIELD_CHARS = 4096
MAX_INGEST_BATCH_SIZE = 500


class EventIngestRequest(BaseModel):
    event_type: str = Field(..., min_length=1, max_length=64)
    event_source: EventSource
    timestamp: Optional[datetime] = Field(default=None, validate_default=True)

    # External sources describe machines by IP, not VEXUS's internal
    # asset id. asset_id is also accepted directly for callers that
    # already know it (e.g. a future proper adapter), but ip_address is
    # the expected common case and is resolved server-side.
    ip_address: Optional[str] = None
    asset_id: Optional[str] = None

    severity: EventSeverity = EventSeverity.INFORMATIONAL
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    description: str = Field(default="", max_length=1024)
    evidence: Any = Field(default_factory=list)
    event_metadata: dict = Field(default_factory=dict)

    @field_validator("event_source")
    @classmethod
    def _validate_source(cls, value: EventSource) -> EventSource:
        if value not in ALLOWED_INGEST_SOURCES:
            allowed = ", ".join(sorted(s.value for s in ALLOWED_INGEST_SOURCES))
            raise ValueError(f"event_source must be one of: {allowed}")
        return value

    @field_validator("timestamp")
    @classmethod
    def _default_timestamp(cls, value: Optional[datetime]) -> datetime:
        if value is None:
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class EventIngestBatch(BaseModel):
    events: list[EventIngestRequest] = Field(..., min_length=1, max_length=MAX_INGEST_BATCH_SIZE)


class IngestedEventResult(BaseModel):
    event_id: str
    event_type: str
    asset_matched: bool


class EventIngestResponse(BaseModel):
    ingested_count: int
    unmatched_asset_count: int
    results: list[IngestedEventResult]
