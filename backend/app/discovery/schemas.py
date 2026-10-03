import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.discovery.collectors import ScanProfile
from app.discovery.models import ScanStatus


class ScanRequest(BaseModel):
    target_ranges: list[str] = Field(min_length=1, max_length=20)
    # Optional scan profile. When omitted, the platform default
    # (Settings.DISCOVERY_DEFAULT_PROFILE, normally `stealth_syn`)
    # is used. The closed-enum ScanProfile restricts the value here
    # at the API boundary — an unknown profile string is rejected
    # with 422 before any subprocess is spawned.
    profile: ScanProfile | None = None


class ScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    target_ranges: list[str]
    status: ScanStatus
    started_at: datetime
    completed_at: datetime | None
    hosts_discovered: int
    new_assets: int
    changed_assets: int
    error_message: str
    # The profile that ran (always populated — defaults to the
    # platform default when not supplied on the request). Surfaces
    # the actual scan technique in scan history so an analyst can
    # see "this scan was stealth_syn, that one was service_version"
    # rather than guessing from the host count alone.
    profile: ScanProfile = ScanProfile.STEALTH_SYN

    @field_validator("target_ranges", mode="before")
    @classmethod
    def _parse_target_ranges(cls, value):
        if isinstance(value, str):
            return json.loads(value)
        return value
