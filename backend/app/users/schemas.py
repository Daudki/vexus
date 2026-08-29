"""
User schemas for API validation.
"""
import re
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

from app.core.security import is_password_strong
from app.users.models import RoleName

# A permissive email-format check. We deliberately avoid pydantic's
# EmailStr/email-validator here: that library hard-rejects "special
# use" TLDs like .local and .internal (no way to opt out), but VEXUS
# is an internal security tool where admin/service accounts routinely
# use addresses like admin@vexus.local (see README quick start and
# scripts/seed.py). This regex only checks basic shape.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_PASSWORD_HINT = (
    "Password must be at least 8 characters and include an uppercase "
    "letter, a lowercase letter, a digit, and a special character."
)


class UserCreate(BaseModel):
    """Schema for creating a user."""
    username: str = Field(..., min_length=3, max_length=50)
    email: str
    password: str = Field(..., min_length=8)
    role: RoleName = RoleName.VIEWER

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        if not _EMAIL_RE.match(value):
            raise ValueError("value is not a valid email address")
        return value

    @field_validator("password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if not is_password_strong(value):
            raise ValueError(_PASSWORD_HINT)
        return value


class UserUpdateRole(BaseModel):
    """Schema for updating a user's role."""
    role: RoleName


class UserUpdateStatus(BaseModel):
    """Schema for activating/deactivating a user."""
    is_active: bool


class UserResetPassword(BaseModel):
    """Schema for an admin-initiated password reset."""
    new_password: str = Field(..., min_length=8)

    @field_validator("new_password")
    @classmethod
    def _validate_password(cls, value: str) -> str:
        if not is_password_strong(value):
            raise ValueError(_PASSWORD_HINT)
        return value


class UserRead(BaseModel):
    """Schema for reading a user."""
    id: str
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime] = None