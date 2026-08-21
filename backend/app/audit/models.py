"""
Audit log model.

Append-only by convention: the repository layer for this table exposes
`create()` only — no update or delete methods are defined anywhere in
the codebase, so tampering would require a deliberate code change, not
an accidental one.
"""
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    actor_username: Mapped[str] = mapped_column(String(64))  # denormalized snapshot at time of action
    action: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "login", "asset.update"
    target_type: Mapped[str] = mapped_column(String(64), default="")
    target_id: Mapped[str] = mapped_column(String(64), default="")
    detail: Mapped[str] = mapped_column(String(1024), default="")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
    success: Mapped[bool] = mapped_column(default=True)
