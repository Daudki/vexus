import re
from datetime import datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from app.users.models import RoleName

# Deliberately format-only (not pydantic's EmailStr / email-validator),
# which rejects reserved-use TLDs like .local, .internal, .corp, .lan —
# exactly the domains internal security tooling commonly runs on.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _validate_email_format(value: str) -> str:
    if not _EMAIL_RE.match(value):
        raise ValueError("must be a valid email address format")
    return value


EmailAddress = Annotated[str, AfterValidator(_validate_email_format)]


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailAddress
    password: str = Field(min_length=10, max_length=128)
    role: RoleName = RoleName.VIEWER


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: EmailAddress
    role: RoleName
    is_active: bool
    created_at: datetime
    last_login: datetime | None = None


class UserUpdateRole(BaseModel):
    role: RoleName
