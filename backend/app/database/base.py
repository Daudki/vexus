"""
Shared SQLAlchemy declarative base and reusable mixins.

Every domain model in the project should inherit from `Base`, and most
should also use `TimestampMixin` / `UUIDPrimaryKeyMixin` so that ID and
timestamp conventions stay consistent platform-wide (this matters once
Discovery, Watch, Detect, etc. all start writing to related tables).
"""
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UUIDPrimaryKeyMixin:
    id: Mapped[str] = mapped_column(
        primary_key=True, default=lambda: str(uuid.uuid4())
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
