"""
User schemas for API validation.
"""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field

from app.users.models import RoleName


class UserCreate(BaseModel):
    """Schema for creating a user."""
    username: str = Field(..., min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(..., min_length=8)
    role: RoleName = RoleName.VIEWER


class UserUpdateRole(BaseModel):
    """Schema for updating a user's role."""
    role: RoleName


class UserRead(BaseModel):
    """Schema for reading a user."""
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None