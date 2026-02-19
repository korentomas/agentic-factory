"""External task watchdog for the Agent Runner.

Monitors running tasks and force-kills those that exceed their
hard timeout (2x the configured timeout_seconds). Also detects
zombie tasks — status=RUNNING but the underlying asyncio task
has already completed.
"""

from __future__ import annotations

import asyncio
import time

import structlog

from apps.runner.audit import AuditLog
from apps.runner.models import TaskState, TaskStatus

logger = structlog.get_logger()

# Hard kill threshold multiplier: tasks exceeding timeout * this factor
# are forcibly terminated by the watchdog.
HARD_KILL_MULTIPLIER: float = 2.0


class TaskWatchdog:
    """Background watchdog that monitors running agent tasks.

    Periodically scans the task store for:
    - **Overtime tasks**: status=RUNNING and elapsed time exceeds
      ``timeout_seconds * 2``. These are force-killed via cancel_event
      and asyncio task cancellation, then marked FAILED.
    - **Zombie tasks**: status=RUNNING but the underlying ``_async_task``
      has already completed (done() returns True). These are logged as
      warnings for investigation.

    Args:
        tasks: Reference to the in-memory task store.
        audit_log: Audit log for recording force-kill events.
        check_interval_seconds: How often to scan (default 30s).
    """

    def __init__(
        self,
        tasks: dict[str, TaskState],
        audit_log: AuditLog,
        check_interval_seconds: float = 30.0,
    ) -> None:
        self._tasks = tasks
        self._audit_log = audit_log
        self._check_interval = check_interval_seconds
        self._bg_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Start the watchdog as a background asyncio task."""
        if self._bg_task is not None and not self._bg_task.done():
            logger.warning("watchdog.already_running")
            return
        self._stop_event.clear()
        self._bg_task = asyncio.create_task(self._run_loop())
        logger.info("watchdog.started", interval=self._check_interval)

    async def stop(self) -> None:
        """Stop the watchdog and wait for it to finish."""
        self._stop_event.set()
        if self._bg_task is not None and not self._bg_task.done():
            self._bg_task.cancel()
            try:
                await self._bg_task
            except asyncio.CancelledError:
                pass
        self._bg_task = None
        logger.info("watchdog.stopped")

    @property
    def is_running(self) -> bool:
        """Return True if the watchdog background task is active."""
        return self._bg_task is not None and not self._bg_task.done()

    async def _run_loop(self) -> None:
        """Main watchdog loop — runs until stopped."""
        while not self._stop_event.is_set():
            try:
                self._check_tasks()
            except Exception:
                logger.exception("watchdog.check_error")
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self._check_interval,
                )
                # stop_event was set — exit the loop
                break
            except TimeoutError:
                # Normal: interval elapsed, loop again
                continue

    def _check_tasks(self) -> None:
        """Scan all tasks for overtime or zombie conditions."""
        now = time.monotonic()
        for task_id, state in list(self._tasks.items()):
            if state.status != TaskStatus.RUNNING:
                continue
            self._check_overtime(task_id, state, now)
            self._check_zombie(task_id, state)

    def _check_overtime(
        self,
        task_id: str,
        state: TaskState,
        now: float,
    ) -> None:
        """Detect and force-kill tasks that exceeded the hard timeout."""
        if state.started_at is None:
            return

        timeout = state.task.timeout_seconds
        hard_limit = timeout * HARD_KILL_MULTIPLIER
        elapsed = now - state.started_at

        if elapsed <= hard_limit:
            return

        logger.warning(
            "watchdog.force_kill",
            task_id=task_id,
            elapsed_seconds=round(elapsed, 1),
            hard_limit_seconds=hard_limit,
            timeout_seconds=timeout,
        )

        # Signal cancellation
        state.cancel_event.set()

        # Cancel the asyncio task
        if state._async_task is not None and not state._async_task.done():
            state._async_task.cancel()

        # Mark as failed
        state.status = TaskStatus.FAILED

        # Record audit event
        self._audit_log.record(
            "watchdog.force_kill",
            task_id=task_id,
            elapsed_seconds=round(elapsed, 1),
            hard_limit_seconds=hard_limit,
        )

    def _check_zombie(self, task_id: str, state: TaskState) -> None:
        """Detect zombie tasks — RUNNING status but asyncio task is done."""
        if state._async_task is None:
            return

        if not state._async_task.done():
            return

        logger.warning(
            "watchdog.zombie_detected",
            task_id=task_id,
            status=state.status.value,
        )
