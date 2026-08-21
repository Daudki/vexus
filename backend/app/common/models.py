"""
Data Quality Warning.

Attached by any module that produces a result under degraded conditions
(a monitoring gap, an unidentified OS, a low-sample-size baseline) so
the result is never presented as complete when it isn't. `subject_type`/
`subject_id` point at whatever the warning concerns (an Asset, a
RiskScore, a dashboard-wide metric, etc.) — kept generic rather than a
foreign key per subject type since the set of subjects will grow.
"""
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class DataQualityWarning(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "data_quality_warnings"

    subject_type: Mapped[str] = mapped_column(String(64), index=True)  # e.g. "asset", "risk_score", "dashboard"
    subject_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    message: Mapped[str] = mapped_column(String(512))  # e.g. "Monitoring unavailable for 27 minutes"
    resolved: Mapped[bool] = mapped_column(default=False)
