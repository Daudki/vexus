"""
Audit log model.

Column names and types mirror the initial alembic migration exactly
(`actor_user_id`, `actor_username`, `target_type`, `target_id`,
`detail`, `ip_address`, `success`) -- see
alembic/versions/273f1f1a6fc9_initial_schema.py.
"""
from sqlalchemy import Boolean, Column, ForeignKey, Index, String

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class AuditLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_logs"

    actor_user_id = Column(String, ForeignKey("users.id"), nullable=True)
    actor_username = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False, index=True)
    target_type = Column(String(64), nullable=False)
    target_id = Column(String(64), nullable=False)
    detail = Column(String(1024), nullable=False)
    ip_address = Column(String(64), nullable=False)
    success = Column(Boolean, nullable=False)

    __table_args__ = (
        Index("ix_audit_logs_target", "target_type", "target_id"),
    )
