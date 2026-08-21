import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.discovery.models import ScanStatus


class ScanRequest(BaseModel):
    target_ranges: list[str] = Field(min_length=1, max_length=20)


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

    @field_validator("target_ranges", mode="before")
    @classmethod
    def _parse_target_ranges(cls, value):
        if isinstance(value, str):
            return json.loads(value)
        return value
