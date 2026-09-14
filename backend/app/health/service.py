from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.health.models import WorkerHeartbeat

# A worker that hasn't reported a successful cycle within this window is
# considered stale even if its last recorded status was "ok" -- e.g. the
# scheduler was stopped/crashed without writing a final "degraded" row.
STALE_WORKER_MINUTES = 15

# Workers the platform expects to see heartbeats from once the background
# scheduler (Settings.SCHEDULER_ENABLED) or manual "run now" endpoints have
# been used at least once. A worker simply not existing yet (never run) is
# reported as "unknown", not "unhealthy" -- it isn't a failure, just data
# that doesn't exist yet.
KNOWN_WORKERS = ["monitoring", "discovery", "detection", "sense"]


class HealthService:
    def __init__(self, db: Session):
        self.db = db

    def check_health(self):
        try:
            self.db.execute(text("SELECT 1"))
            db_status = "healthy"
        except Exception:
            db_status = "unhealthy"

        workers = self._worker_statuses()
        overall = "healthy" if db_status == "healthy" else "unhealthy"

        return {
            "status": overall,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "database": {"status": db_status},
                "workers": workers,
            },
        }

    def _worker_statuses(self) -> dict:
        now = datetime.now(timezone.utc)
        heartbeats = {hb.worker_name: hb for hb in self.db.query(WorkerHeartbeat).all()}

        result = {}
        for worker_name in KNOWN_WORKERS:
            hb = heartbeats.get(worker_name)
            if hb is None:
                result[worker_name] = {"status": "unknown", "detail": "No cycle has run yet."}
                continue

            stale = hb.last_success_at is None or (
                now - _as_aware(hb.last_success_at) > timedelta(minutes=STALE_WORKER_MINUTES)
            )
            status = "degraded" if (stale and hb.status == "ok") else hb.status
            result[worker_name] = {
                "status": status,
                "detail": hb.detail,
                "last_success_at": hb.last_success_at.isoformat() if hb.last_success_at else None,
            }
        return result


def _as_aware(value: datetime) -> datetime:
    """SQLite drops tzinfo on round-trip; treat naive timestamps as UTC
    rather than letting the subtraction above raise."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
