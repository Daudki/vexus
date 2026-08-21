"""
ScanJob — the audit trail for discovery scans.

Every scan, regardless of outcome, gets a row: who initiated it, the
exact target ranges requested, and its status. Refused scans (scope
violation) are recorded too, not just successful ones — this is what
lets an analyst later answer "did anyone try to scan outside our
authorized ranges?"
"""
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class ScanStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUSED = "refused"  # scope validation failed — no collector was ever invoked


class ScanJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scan_jobs"

    initiated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_ranges: Mapped[str] = mapped_column(String(1024))  # JSON-encoded list[str]

    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.RUNNING)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    hosts_discovered: Mapped[int] = mapped_column(Integer, default=0)
    new_assets: Mapped[int] = mapped_column(Integer, default=0)
    changed_assets: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str] = mapped_column(String(1024), default="")
