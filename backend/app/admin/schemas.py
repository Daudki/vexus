from typing import Optional, List
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from enum import Enum


class RoleName(str, Enum):
    ADMIN = "admin"
    ANALYST = "analyst"
    VIEWER = "viewer"


# User schemas
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=4)
    full_name: Optional[str] = None
    role: RoleName = RoleName.VIEWER


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None
    password: Optional[str] = Field(None, min_length=4)
    role: Optional[RoleName] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    role: Optional[str]
    created_at: Optional[str]
    last_login: Optional[str]


# Role schemas
class RoleCreate(BaseModel):
    name: str = Field(..., min_length=3, max_length=50)
    description: Optional[str] = None


class RoleUpdate(BaseModel):
    description: Optional[str] = None


class RoleResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    created_at: Optional[str]


# Audit schemas
class AuditLogResponse(BaseModel):
    id: str
    user_id: Optional[str]
    action: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    details: Optional[dict]
    ip_address: Optional[str]
    timestamp: str


# Settings schemas
class SystemSettings(BaseModel):
    allow_registration: bool = True
    require_email_verification: bool = False
    default_role: str = "viewer"
    session_timeout_minutes: int = 30
    max_login_attempts: int = 5
    lockout_duration_minutes: int = 15


class SettingsUpdate(BaseModel):
    allow_registration: Optional[bool] = None
    require_email_verification: Optional[bool] = None
    default_role: Optional[str] = None
    session_timeout_minutes: Optional[int] = None
    max_login_attempts: Optional[int] = None
    lockout_duration_minutes: Optional[int] = None


# Stats schemas
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