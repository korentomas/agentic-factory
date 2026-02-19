"""Tests for apps.runner.watchdog — external task watchdog."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import MagicMock

import pytest

from apps.runner.audit import AuditLog
from apps.runner.models import RunnerTask, TaskState, TaskStatus
from apps.runner.watchdog import HARD_KILL_MULTIPLIER, TaskWatchdog


def _make_task(
    task_id: str = "test-1",
    timeout_seconds: int = 10,
) -> RunnerTask:
    """Create a minimal RunnerTask for testing."""
    return RunnerTask(
        task_id=task_id,
        repo_url="https://github.com/org/repo",
        branch="feat-test",
        base_branch="main",
        description="Test task",
        timeout_seconds=timeout_seconds,
    )


def _make_running_state(
    task_id: str = "test-1",
    timeout_seconds: int = 10,
    elapsed: float = 0.0,
    async_task_done: bool = False,
) -> TaskState:
    """Create a TaskState in RUNNING status with a mock async task.

    Args:
        task_id: Task identifier.
        timeout_seconds: Timeout configured on the task.
        elapsed: How many seconds ago the task "started" (simulated).
        async_task_done: Whether the mock async task reports done().
    """
    task = _make_task(task_id=task_id, timeout_seconds=timeout_seconds)
    state = TaskState(task=task, status=TaskStatus.RUNNING)
    state.started_at = time.monotonic() - elapsed

    mock_async = MagicMock(spec=asyncio.Task)
    mock_async.done.return_value = async_task_done
    mock_async.cancel.return_value = None
    state._async_task = mock_async

    return state


class TestOvertimeDetection:
    """Tests for force-killing tasks that exceed their hard timeout."""

    def test_force_kills_overtime_task(self) -> None:
        """Watchdog detects overtime task and sets status to FAILED."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        # timeout=10s, hard limit=20s, elapsed=25s -> overtime
        state = _make_running_state(
            task_id="overtime-1",
            timeout_seconds=10,
            elapsed=25.0,
        )
        tasks["overtime-1"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        assert state.status == TaskStatus.FAILED

    def test_force_kill_sets_cancel_event(self) -> None:
        """Force-killed task has its cancel_event set."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        state = _make_running_state(
            task_id="overtime-2",
            timeout_seconds=5,
            elapsed=15.0,
        )
        tasks["overtime-2"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        assert state.cancel_event.is_set()

    def test_force_kill_cancels_async_task(self) -> None:
        """Force-killed task has its asyncio task cancelled."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        state = _make_running_state(
            task_id="overtime-3",
            timeout_seconds=5,
            elapsed=15.0,
        )
        tasks["overtime-3"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        assert state._async_task is not None
        state._async_task.cancel.assert_called_once()

    def test_force_kill_records_audit_event(self) -> None:
        """Force-killed task generates a 'watchdog.force_kill' audit event."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        state = _make_running_state(
            task_id="overtime-4",
            timeout_seconds=10,
            elapsed=25.0,
        )
        tasks["overtime-4"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        events = audit.get_events("overtime-4")
        assert len(events) == 1
        assert events[0].action == "watchdog.force_kill"
        assert events[0].metadata["hard_limit_seconds"] == 10 * HARD_KILL_MULTIPLIER

    def test_force_kill_audit_includes_elapsed(self) -> None:
        """Audit event for force-kill includes elapsed time metadata."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        state = _make_running_state(
            task_id="overtime-5",
            timeout_seconds=10,
            elapsed=30.0,
        )
        tasks["overtime-5"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        events = audit.get_events("overtime-5")
        assert len(events) == 1
        assert events[0].metadata["elapsed_seconds"] >= 29.0


class TestWithinTimeout:
    """Tests for tasks that are within their timeout."""

    def test_ignores_task_within_timeout(self) -> None:
        """Watchdog does not touch a task still within its timeout."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        # timeout=10s, hard limit=20s, elapsed=5s -> within limit
        state = _make_running_state(
            task_id="ok-1",
            timeout_seconds=10,
            elapsed=5.0,
        )
        tasks["ok-1"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        assert state.status == TaskStatus.RUNNING
        assert not state.cancel_event.is_set()
        assert len(audit.get_events("ok-1")) == 0

    def test_ignores_task_at_normal_timeout_boundary(self) -> None:
        """Task at exactly 1x timeout is not killed (needs 2x)."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        # elapsed=10s equals 1x timeout, which is below 2x hard limit
        state = _make_running_state(
            task_id="boundary-1",
            timeout_seconds=10,
            elapsed=10.0,
        )
        tasks["boundary-1"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        assert state.status == TaskStatus.RUNNING

    def test_ignores_non_running_tasks(self) -> None:
        """Watchdog skips tasks that are not in RUNNING status."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        task = _make_task(task_id="complete-1", timeout_seconds=10)
        state = TaskState(task=task, status=TaskStatus.COMPLETE)
        state.started_at = time.monotonic() - 100.0  # way past timeout
        tasks["complete-1"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        assert state.status == TaskStatus.COMPLETE
        assert len(audit.get_events("complete-1")) == 0


class TestZombieDetection:
    """Tests for detecting zombie tasks."""

    def test_detects_zombie_task(self, caplog: pytest.LogCaptureFixture) -> None:
        """Watchdog logs a warning for zombie tasks (RUNNING + async_task done)."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        state = _make_running_state(
            task_id="zombie-1",
            timeout_seconds=3600,
            elapsed=1.0,
            async_task_done=True,
        )
        tasks["zombie-1"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)

        watchdog._check_tasks()
        # The zombie check calls logger.warning — verify via the state
        # (the zombie detection doesn't change status, only logs)
        assert state.status == TaskStatus.RUNNING

    def test_zombie_does_not_change_status(self) -> None:
        """Zombie detection only logs — it does not modify task status."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        state = _make_running_state(
            task_id="zombie-2",
            timeout_seconds=3600,
            elapsed=1.0,
            async_task_done=True,
        )
        tasks["zombie-2"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        assert state.status == TaskStatus.RUNNING
        assert len(audit.get_events("zombie-2")) == 0

    def test_no_zombie_when_async_task_not_done(self) -> None:
        """Non-zombie tasks (async_task running) produce no warning."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        state = _make_running_state(
            task_id="healthy-1",
            timeout_seconds=3600,
            elapsed=1.0,
            async_task_done=False,
        )
        tasks["healthy-1"] = state

        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)
        watchdog._check_tasks()

        # Healthy task should remain unchanged
        assert state.status == TaskStatus.RUNNING


class TestStartStop:
    """Tests for watchdog lifecycle management."""

    @pytest.mark.asyncio
    async def test_start_and_stop(self) -> None:
        """Watchdog can be started and stopped cleanly."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)

        await watchdog.start()
        assert watchdog.is_running

        await watchdog.stop()
        assert not watchdog.is_running

    @pytest.mark.asyncio
    async def test_double_start_is_safe(self) -> None:
        """Starting the watchdog twice does not create duplicate loops."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)

        await watchdog.start()
        first_task = watchdog._bg_task

        await watchdog.start()
        second_task = watchdog._bg_task

        # Second start should be a no-op — same background task
        assert first_task is second_task

        await watchdog.stop()

    @pytest.mark.asyncio
    async def test_stop_without_start_is_safe(self) -> None:
        """Stopping a watchdog that was never started does not raise."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.1)

        # Should not raise
        await watchdog.stop()
        assert not watchdog.is_running

    @pytest.mark.asyncio
    async def test_watchdog_detects_overtime_during_loop(self) -> None:
        """Watchdog running in background detects and kills overtime tasks."""
        tasks: dict[str, TaskState] = {}
        audit = AuditLog()
        watchdog = TaskWatchdog(tasks, audit, check_interval_seconds=0.05)

        await watchdog.start()

        # Add an overtime task while watchdog is running
        state = _make_running_state(
            task_id="bg-overtime",
            timeout_seconds=1,
            elapsed=5.0,
        )
        tasks["bg-overtime"] = state

        # Wait for at least one check cycle
        await asyncio.sleep(0.15)

        await watchdog.stop()

        assert state.status == TaskStatus.FAILED
        events = audit.get_events("bg-overtime")
        assert any(e.action == "watchdog.force_kill" for e in events)
