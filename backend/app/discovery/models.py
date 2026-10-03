"""
ScanJob — the audit trail for discovery scans.

Every scan, regardless of outcome, gets a row: who initiated it, the
exact target ranges requested, the scan profile that ran, and its
status. Refused scans (scope violation) are recorded too, not just
successful ones — this is what lets an analyst later answer "did anyone
try to scan outside our authorized ranges?"
"""
import enum

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.assets.service import DiscoveredHost  # noqa: F401  (kept for back-compat importers)
from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.discovery.collectors import ScanProfile


class ScanStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUSED = "refused"  # scope validation failed — no collector was ever invoked


class ScanJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "scan_jobs"

    initiated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    target_ranges: Mapped[str] = mapped_column(String(1024))  # JSON-encoded list[str]

    # The scan profile that ran for this job. Stored as the enum value
    # (e.g. `stealth_syn`), not the raw nmap flag list — the profile is
    # the operator-facing concept, the flag list is an implementation
    # detail of NmapCollector. Defaults to the platform default at the
    # service layer; the column itself defaults to STEALTH_SYN so a
    # pre-migration ScanJob row that didn't carry the field still has a
    # defensible value rather than NULL.
    profile: Mapped[ScanProfile] = mapped_column(
        Enum(ScanProfile, name="scan_profile"),
        nullable=False,
        default=ScanProfile.STEALTH_SYN,
    )

    status: Mapped[ScanStatus] = mapped_column(Enum(ScanStatus), default=ScanStatus.RUNNING)
    started_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    hosts_discovered: Mapped[int] = mapped_column(Integer, default=0)
    new_assets: Mapped[int] = mapped_column(Integer, default=0)
    changed_assets: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str] = mapped_column(String(1024), default="")
