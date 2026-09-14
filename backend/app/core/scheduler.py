"""
Background scheduler (V2 gap closure).

docs/architecture/V2_ARCHITECTURE_AUDIT.md lists "No durable background
worker/scheduler exists for recurring discovery, monitoring, detection,
or baseline calculation" as the top V2 gap. This module closes it with a
minimal, dependency-free, in-process asyncio scheduler rather than
pulling in Celery/APScheduler/etc. — a single-process background loop is
enough for the current deployment shape (one API process, SQLite or
Postgres), and it reuses the exact same service methods the manual
"poll now" / "run now" API endpoints already call (see
app/monitoring/router.py, app/detection/router.py,
app/discovery/router.py, app/sense/router.py), so there is exactly one
implementation of each behavior — not a scheduler-specific copy (VEXUS
v2 Development Rules, "do not introduce a second implementation of the
same subsystem").

Off by default (Settings.SCHEDULER_ENABLED). Every existing test's DB
access goes through the `get_db` FastAPI dependency, which conftest.py
overrides to a shared in-memory session — but a background task started
outside of request handling can't go through that override, so it uses
`SessionLocal` (the real, configured engine) directly. If the scheduler
ever started by default, every test run (which triggers FastAPI's
lifespan via `with TestClient(app)`) would launch real background loops
against whatever DATABASE_URL happens to be set for the test process --
a different database than the one the test itself is asserting against.
Requiring an explicit opt-in avoids that entirely.
"""
from __future__ import annotations

import asyncio
import logging

from app.database.session import SessionLocal

logger = logging.getLogger("vexus.scheduler")


async def _loop(name: str, interval_seconds: int, run_once_fn) -> None:
    """Sleep, then run once, forever — never let one bad cycle kill the
    loop (VEXUS v2 Development Rules, "do not silently ignore failures":
    failures are logged, not swallowed, but they also must not stop
    future cycles from running)."""
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            run_once_fn()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 — log and keep looping, see docstring
            logger.exception("Background job '%s' failed; will retry next cycle.", name)


def _run_monitoring_poll() -> None:
    from app.monitoring.router import get_monitoring_collector
    from app.monitoring.service import MonitoringService

    db = SessionLocal()
    try:
        MonitoringService(db, get_monitoring_collector()).poll_all()
    finally:
        db.close()


def _run_detection() -> None:
    from app.detection.service import DetectionEngine

    db = SessionLocal()
    try:
        DetectionEngine(db).run(actor=None, ip_address="scheduler")
    finally:
        db.close()


def _run_discovery_scan(target_ranges: list[str]) -> None:
    from app.discovery.router import get_discovery_collector
    from app.discovery.service import DiscoveryService

    db = SessionLocal()
    try:
        DiscoveryService(db, get_discovery_collector()).run_scan(
            target_ranges, initiated_by=None, ip_address="scheduler"
        )
    finally:
        db.close()


def _run_sense_evaluation() -> None:
    from app.sense.service import SenseService

    db = SessionLocal()
    try:
        SenseService(db).evaluate_all_assets()
    finally:
        db.close()


def start_background_tasks(settings) -> list[asyncio.Task]:
    """Start one independent loop per job type so a slow/failing job
    (e.g. discovery against a large range) never blocks the others.
    Returns the created tasks so the caller can cancel them on shutdown."""
    tasks: list[asyncio.Task] = [
        asyncio.create_task(
            _loop("monitoring.poll", settings.SCHEDULER_MONITORING_INTERVAL_SECONDS, _run_monitoring_poll),
            name="scheduler-monitoring",
        ),
        asyncio.create_task(
            _loop("detection.run", settings.SCHEDULER_DETECTION_INTERVAL_SECONDS, _run_detection),
            name="scheduler-detection",
        ),
        asyncio.create_task(
            _loop("sense.evaluate_all", settings.SCHEDULER_SENSE_INTERVAL_SECONDS, _run_sense_evaluation),
            name="scheduler-sense",
        ),
    ]

    # Discovery must never assume every reachable network is an
    # authorized target (VEXUS v2 Development Rules) — only schedule
    # recurring scans if the deployment has actually configured
    # authorized ranges. run_scan() would also refuse an empty range
    # list, but skipping it here avoids a scan_refused audit entry and
    # a "degraded" heartbeat every single cycle for the common case of
    # a deployment that hasn't configured discovery yet.
    scan_ranges = settings.authorized_scan_ranges_list
    if scan_ranges:
        tasks.append(
            asyncio.create_task(
                _loop(
                    "discovery.scan",
                    settings.SCHEDULER_DISCOVERY_INTERVAL_SECONDS,
                    lambda: _run_discovery_scan(scan_ranges),
                ),
                name="scheduler-discovery",
            )
        )
    else:
        logger.info("Scheduled discovery disabled: no AUTHORIZED_SCAN_RANGES configured.")

    return tasks


async def stop_background_tasks(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
