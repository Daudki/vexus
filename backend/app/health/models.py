"""
Platform self-monitoring ("VEXUS Health").

Workers (discovery, monitoring — added in Phases 2/3) write a heartbeat
row here every time they complete a cycle. The /health endpoint reads
this table to answer "is VEXUS actually collecting data?" rather than
just "is the API process up?".
"""
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class WorkerHeartbeat(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "worker_heartbeats"

    worker_name: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # e.g. "discovery", "monitoring"
    last_success_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown")  # ok | degraded | stopped | unknown
    detail: Mapped[str] = mapped_column(String(512), default="")
