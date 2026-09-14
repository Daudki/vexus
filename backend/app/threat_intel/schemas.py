from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class VulnerabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    cve_id: str
    source: str
    description: str
    cvss_score: float | None
    cvss_severity: str | None
    cvss_version: str | None
    published_at: datetime | None
    last_modified_at: datetime | None
    cwe_ids: list[str]
    affected_cpes: list[str]
    references: list[str]
    is_rejected: bool


class VulnerabilityListResponse(BaseModel):
    items: list[VulnerabilityRead]
    total: int


class SyncCVEResponse(BaseModel):
    cve_id: str
    created: bool
    updated: bool
    event_id: str | None
    source: str


class ThreatIntelStatus(BaseModel):
    provider: str
    configured: bool
