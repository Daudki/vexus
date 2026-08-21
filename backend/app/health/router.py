"""
Health and readiness endpoints.

/health/live  -> is the process up at all (for orchestrators/load balancers)
/health/ready -> is the DB reachable (used before accepting real traffic)
/health/status -> the full VEXUS Health picture for the dashboard status strip
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.database.session import get_db
from app.health.models import WorkerHeartbeat

router = APIRouter(prefix="/api/v1/health", tags=["health"])
settings = get_settings()

STALE_AFTER = timedelta(minutes=15)


@router.get("/live")
def liveness() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def readiness(db: Session = Depends(get_db)) -> dict:
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False

    return {"status": "ok" if db_ok else "unavailable", "database": db_ok}


@router.get("/status")
def platform_status(db: Session = Depends(get_db)) -> dict:
    """
    Full self-monitoring snapshot: DB, worker heartbeats, and AI provider
    configuration. This is what the dashboard's 🟢/🟡/🔴 status strip reads.
    """
    now = datetime.now(timezone.utc)

    try:
        db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception:
        db_status = "stopped"

    heartbeats = db.query(WorkerHeartbeat).all()
    workers = {}
    for hb in heartbeats:
        if hb.last_success_at is None:
            workers[hb.worker_name] = "stopped"
        elif now - hb.last_success_at.replace(tzinfo=timezone.utc) > STALE_AFTER:
            workers[hb.worker_name] = "degraded"
        else:
            workers[hb.worker_name] = "ok"

    # Workers that have never registered at all (e.g. Phase 2/3 not yet
    # deployed) are reported explicitly rather than silently omitted.
    for expected in ("discovery", "monitoring", "detection", "risk"):
        workers.setdefault(expected, "not_configured")

    ai_status = "not_configured" if settings.AI_PROVIDER == "none" else "configured"

    return {
        "database": db_status,
        "workers": workers,
        "ai_provider": ai_status,
        "checked_at": now.isoformat(),
    }
