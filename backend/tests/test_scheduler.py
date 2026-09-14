import asyncio
from types import SimpleNamespace

import pytest

from app.core.scheduler import _loop, start_background_tasks, stop_background_tasks


def _settings(**overrides):
    base = dict(
        SCHEDULER_MONITORING_INTERVAL_SECONDS=9999,
        SCHEDULER_DETECTION_INTERVAL_SECONDS=9999,
        SCHEDULER_DISCOVERY_INTERVAL_SECONDS=9999,
        SCHEDULER_SENSE_INTERVAL_SECONDS=9999,
        AUTHORIZED_SCAN_RANGES=[],
    )
    base.update(overrides)
    ns = SimpleNamespace(**base)
    ns.authorized_scan_ranges_list = base["AUTHORIZED_SCAN_RANGES"]
    return ns


@pytest.mark.asyncio
async def test_start_background_tasks_skips_discovery_when_no_authorized_ranges():
    settings = _settings(AUTHORIZED_SCAN_RANGES=[])
    tasks = start_background_tasks(settings)
    try:
        names = {task.get_name() for task in tasks}
        assert "scheduler-discovery" not in names
        assert {"scheduler-monitoring", "scheduler-detection", "scheduler-sense"} <= names
    finally:
        await stop_background_tasks(tasks)


@pytest.mark.asyncio
async def test_start_background_tasks_includes_discovery_when_ranges_configured():
    settings = _settings(AUTHORIZED_SCAN_RANGES=["10.0.0.0/24"])
    tasks = start_background_tasks(settings)
    try:
        names = {task.get_name() for task in tasks}
        assert "scheduler-discovery" in names
    finally:
        await stop_background_tasks(tasks)


@pytest.mark.asyncio
async def test_loop_survives_a_failing_cycle_and_runs_again():
    """A single bad cycle (e.g. a transient DB error) must not kill the
    loop -- VEXUS v2 Development Rules explicitly forbid silently
    swallowing failures, but the fix for "don't swallow" is "log it",
    not "let it crash the whole background loop"."""
    call_count = 0

    def flaky():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated transient failure")

    task = asyncio.create_task(_loop("test-job", 0, flaky))
    try:
        # Give the loop a few cycles to run: first raises, second should
        # still execute because the loop caught the first exception.
        for _ in range(50):
            await asyncio.sleep(0.01)
            if call_count >= 2:
                break
        assert call_count >= 2
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_stop_background_tasks_cancels_cleanly():
    settings = _settings(AUTHORIZED_SCAN_RANGES=[])
    tasks = start_background_tasks(settings)
    await stop_background_tasks(tasks)
    assert all(task.done() for task in tasks)
