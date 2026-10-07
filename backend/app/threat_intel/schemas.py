from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.threat_intel.models import VulnerabilityMatchConfidence


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


class AssetVulnerabilityCreate(BaseModel):
    cve_id: str = Field(min_length=8, max_length=32, pattern=r"^(?i:CVE)-\d{4}-\d{4,}$")


class AssetVulnerabilityRead(BaseModel):
    id: str
    asset_id: str
    cve_id: str
    cvss_score: float | None
    cvss_severity: str | None
    is_rejected: bool
    confidence: VulnerabilityMatchConfidence
    match_source: str
    created_at: datetime


class MatchSummaryRead(BaseModel):
    assets_evaluated: int
    links_created: int
    links_removed: int
