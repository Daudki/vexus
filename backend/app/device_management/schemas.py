from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.device_management.models import DeviceActionType, DeviceTaskStatus, ManagedDeviceStatus


class ManagedDeviceRead(BaseModel):
    id: str
    asset_id: str
    status: ManagedDeviceStatus
    last_checkin_at: datetime | None
    agent_version: str | None
    reported_os: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EnrollmentIssued(BaseModel):
    device: ManagedDeviceRead
    enrollment_token: str
    expires_at: datetime


class AgentEnrollRequest(BaseModel):
    enrollment_token: str
    agent_version: str | None = None
    reported_os: str | None = None


class AgentEnrollResponse(BaseModel):
    agent_token: str
    device_id: str


class DeviceTaskRead(BaseModel):
    id: str
    managed_device_id: str
    action_type: DeviceActionType
    status: DeviceTaskStatus
    result: str
    error_message: str
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DeviceTaskCreate(BaseModel):
    action_type: DeviceActionType
    params: dict[str, Any] = Field(default_factory=dict)
    confirm: bool = False


class AgentTaskResult(BaseModel):
    success: bool
    result: str = ""
    error_message: str = ""
