"""
Admin-only schemas.

User/role/audit-log CRUD lives at /api/v1/users and /api/v1/audit-logs
(see app/users/router.py and app/audit/router.py) — this module only
covers admin functionality that isn't duplicated there: authorized
scan ranges and the system stats dashboard.
"""
from typing import List

from pydantic import BaseModel, Field


class ScanRangesUpdate(BaseModel):
    ranges: List[str] = Field(default_factory=list)


class ScanRangesResponse(BaseModel):
    ranges: List[str] = Field(default_factory=list)


class SystemStats(BaseModel):
    total_users: int
    active_users: int
    total_assets: int
    active_assets: int
    total_alerts: int
    new_alerts: int
    total_incidents: int
    open_incidents: int
    health_status: str
