from datetime import datetime, timedelta, timezone

from app.health.models import WorkerHeartbeat
from app.health.service import HealthService


def test_health_reports_unknown_for_workers_that_never_ran(db_session):
    result = HealthService(db_session).check_health()
    workers = result["components"]["workers"]

    assert workers["monitoring"]["status"] == "unknown"
    assert workers["discovery"]["status"] == "unknown"
    assert workers["detection"]["status"] == "unknown"
    assert workers["sense"]["status"] == "unknown"


def test_health_reports_ok_for_a_recent_successful_worker(db_session):
    now = datetime.now(timezone.utc)
    db_session.add(
        WorkerHeartbeat(worker_name="monitoring", last_success_at=now, status="ok", detail="3 assets polled")
    )
    db_session.commit()

    result = HealthService(db_session).check_health()
    assert result["components"]["workers"]["monitoring"]["status"] == "ok"
    assert result["components"]["workers"]["monitoring"]["detail"] == "3 assets polled"


def test_health_downgrades_stale_ok_heartbeat_to_degraded(db_session):
    """A worker that reported "ok" 30 minutes ago (with nothing since)
    shouldn't keep showing as healthy forever -- the scheduler may have
    crashed or been stopped without writing a final status."""
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=30)
    db_session.add(
        WorkerHeartbeat(worker_name="detection", last_success_at=stale_time, status="ok", detail="old cycle")
    )
    db_session.commit()

    result = HealthService(db_session).check_health()
    assert result["components"]["workers"]["detection"]["status"] == "degraded"


def test_health_preserves_explicit_degraded_status(db_session):
    now = datetime.now(timezone.utc)
    db_session.add(
        WorkerHeartbeat(worker_name="discovery", last_success_at=now, status="degraded", detail="nmap not found")
    )
    db_session.commit()

    result = HealthService(db_session).check_health()
    assert result["components"]["workers"]["discovery"]["status"] == "degraded"


def test_health_endpoint_includes_workers(client):
    resp = client.get("/health/")
    assert resp.status_code == 200
    body = resp.json()
    assert "workers" in body["components"]
    assert set(body["components"]["workers"].keys()) == {"monitoring", "discovery", "detection", "sense"}
