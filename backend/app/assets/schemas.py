from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.assets.models import AssetChangeType, AssetCriticality, AssetStatus, AssetTrustStatus


class AssetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    ip_address: str | None
    mac_address: str | None
    hostname: str | None
    device_type: str | None
    operating_system: str | None
    vendor: str | None
    status: AssetStatus
    criticality: AssetCriticality
    trust_status: AssetTrustStatus
    owner: str | None
    first_seen: datetime
    last_seen: datetime
    risk_score: float


class AssetUpdate(BaseModel):
    """Analyst-editable metadata. Fields discovery owns (ip/mac/hostname/os)
    are intentionally not editable here — they come from observed evidence,
    not manual entry (Evidence First)."""

    device_type: str | None = None
    owner: str | None = None
    criticality: AssetCriticality | None = None
    trust_status: AssetTrustStatus | None = None


class AssetHistoryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    change_type: AssetChangeType
    previous_value: str
    new_value: str
    source: str
    changed_at: datetime


class AssetListParams(BaseModel):
    search: str | None = None  # matches hostname or ip_address
    status: AssetStatus | None = None
    trust_status: AssetTrustStatus | None = None
    criticality: AssetCriticality | None = None
    sort_by: str = Field(default="last_seen", pattern="^(last_seen|first_seen|risk_score|hostname)$")
    sort_desc: bool = True
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)
