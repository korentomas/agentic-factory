"""Tests for ErrorRouter integration in the Runner."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from apps.runner.main import _execute_task
from apps.runner.models import RunnerTask, TaskState, TaskStatus

_WS = "apps.runner.main.create_workspace"
_ROUTER = "apps.runner.main._error_router"
_CLEANUP = "apps.runner.main.cleanup_workspace"


@pytest.fixture
def runner_task() -> RunnerTask:
    return RunnerTask(
        task_id="test-err-1",
        repo_url="https://github.com/test/repo",
        branch="test-branch",
        base_branch="main",
        description="test task",
    )


@pytest.fixture
def task_state(runner_task: RunnerTask) -> TaskState:
    return TaskState(task=runner_task)


class TestRunnerErrorRouterIntegration:
    @pytest.mark.asyncio
    async def test_error_router_called_on_generic_failure(
        self, task_state: TaskState,
    ) -> None:
        """When _execute_task hits a generic Exception, ErrorRouter.handle() is called."""
        mock_handle = AsyncMock()
        err = RuntimeError("boom")

        with (
            patch(_WS, new_callable=AsyncMock, side_effect=err),
            patch(_ROUTER) as mock_router,
            patch(_CLEANUP, new_callable=AsyncMock),
        ):
            mock_router.handle = mock_handle
            await _execute_task(task_state)

        assert task_state.status == TaskStatus.FAILED
        mock_handle.assert_called_once()
        args = mock_handle.call_args[0]
        assert isinstance(args[0], RuntimeError)

    @pytest.mark.asyncio
    async def test_error_router_failure_doesnt_crash_task(
        self, task_state: TaskState,
    ) -> None:
        """If ErrorRouter.handle() raises, the task still completes as FAILED."""
        mock_handle = AsyncMock(
            side_effect=RuntimeError("router broken"),
        )

        with (
            patch(_WS, new_callable=AsyncMock, side_effect=ValueError("bad")),
            patch(_ROUTER) as mock_router,
            patch(_CLEANUP, new_callable=AsyncMock),
        ):
            mock_router.handle = mock_handle
            await _execute_task(task_state)

        assert task_state.status == TaskStatus.FAILED
        assert "bad" in task_state.result.error_message

    @pytest.mark.asyncio
    async def test_error_router_receives_correct_context(
        self, task_state: TaskState,
    ) -> None:
        """ErrorRouter.handle() receives an ErrorContext with correct fields."""
        mock_handle = AsyncMock()
        err = RuntimeError("test error")

        with (
            patch(_WS, new_callable=AsyncMock, side_effect=err),
            patch(_ROUTER) as mock_router,
            patch(_CLEANUP, new_callable=AsyncMock),
        ):
            mock_router.handle = mock_handle
            await _execute_task(task_state)

        ctx = mock_handle.call_args[0][1]
        assert ctx.component == "runner"
        assert ctx.task_id == "test-err-1"

    @pytest.mark.asyncio
    async def test_error_router_called_on_circuit_open(self) -> None:
        """When a CircuitOpenError occurs, ErrorRouter.handle() is called."""
        from apps.runner.circuit_breaker import CircuitOpenError

        task = RunnerTask(
            task_id="test-circuit-1",
            repo_url="https://github.com/test/repo",
            branch="test-branch",
            base_branch="main",
            description="test task",
        )
        state = TaskState(task=task)
        mock_handle = AsyncMock()
        err = CircuitOpenError("claude-code", 30.0)

        with (
            patch(_WS, new_callable=AsyncMock, side_effect=err),
            patch(_ROUTER) as mock_router,
            patch(_CLEANUP, new_callable=AsyncMock),
        ):
            mock_router.handle = mock_handle
            await _execute_task(state)

        assert state.status == TaskStatus.FAILED
        mock_handle.assert_called_once()
        exc_arg = mock_handle.call_args[0][0]
        assert isinstance(exc_arg, CircuitOpenError)

    @pytest.mark.asyncio
    async def test_error_router_called_on_budget_exceeded(self) -> None:
        """When a BudgetExceededError occurs, ErrorRouter.handle() is called."""
        from apps.runner.budget import BudgetExceededError

        task = RunnerTask(
            task_id="test-budget-1",
            repo_url="https://github.com/test/repo",
            branch="test-branch",
            base_branch="main",
            description="test task",
        )
        state = TaskState(task=task)
        mock_handle = AsyncMock()
        err = BudgetExceededError(spent=15.0, limit=10.0)

        with (
            patch(_WS, new_callable=AsyncMock, side_effect=err),
            patch(_ROUTER) as mock_router,
            patch(_CLEANUP, new_callable=AsyncMock),
        ):
            mock_router.handle = mock_handle
            await _execute_task(state)

        assert state.status == TaskStatus.FAILED
        mock_handle.assert_called_once()
        exc_arg = mock_handle.call_args[0][0]
        assert isinstance(exc_arg, BudgetExceededError)
