"""Tests for the centralized error router."""

from __future__ import annotations

from unittest.mock import AsyncMock

import httpx
import pytest

from apps.orchestrator.error_router import (
    ErrorAction,
    ErrorCategory,
    ErrorContext,
    ErrorRouter,
    _backoff,
    classify_error,
)
from apps.runner.budget import BudgetExceededError
from apps.runner.circuit_breaker import CircuitOpenError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_http_error(status_code: int) -> httpx.HTTPStatusError:
    """Build an HTTPStatusError with the given status code."""
    request = httpx.Request("GET", "https://api.example.com/v1/test")
    response = httpx.Response(status_code, request=request)
    return httpx.HTTPStatusError(
        f"{status_code} error",
        request=request,
        response=response,
    )


def _ctx(**overrides: object) -> ErrorContext:
    """Convenience: create an ErrorContext with sensible defaults."""
    defaults: dict[str, object] = {"component": "test"}
    defaults.update(overrides)
    return ErrorContext(**defaults)  # type: ignore[arg-type]


# ===================================================================
# ErrorCategory enum
# ===================================================================

class TestErrorCategory:
    def test_transient_value(self) -> None:
        assert ErrorCategory.TRANSIENT == "transient"

    def test_permanent_value(self) -> None:
        assert ErrorCategory.PERMANENT == "permanent"

    def test_unknown_value(self) -> None:
        assert ErrorCategory.UNKNOWN == "unknown"


# ===================================================================
# ErrorContext creation
# ===================================================================

class TestErrorContext:
    def test_minimal_creation(self) -> None:
        ctx = ErrorContext(component="runner")
        assert ctx.component == "runner"
        assert ctx.task_id is None
        assert ctx.retry_count == 0
        assert ctx.max_retries == 3

    def test_full_creation(self) -> None:
        ctx = ErrorContext(
            component="orchestrator",
            task_id="task-42",
            engine="claude-code",
            model="claude-opus-4",
            stage="write",
            user_tier="team",
            execution_path="/tmp/workspace",
            stderr_tail="some error text",
            stdout_tail="some output",
            retry_count=2,
            max_retries=5,
        )
        assert ctx.component == "orchestrator"
        assert ctx.task_id == "task-42"
        assert ctx.engine == "claude-code"
        assert ctx.model == "claude-opus-4"
        assert ctx.stage == "write"
        assert ctx.user_tier == "team"
        assert ctx.execution_path == "/tmp/workspace"
        assert ctx.stderr_tail == "some error text"
        assert ctx.stdout_tail == "some output"
        assert ctx.retry_count == 2
        assert ctx.max_retries == 5


# ===================================================================
# HTTP error classification
# ===================================================================

class TestHttpClassification:
    def test_429_is_transient(self) -> None:
        err = _make_http_error(429)
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_502_is_transient(self) -> None:
        err = _make_http_error(502)
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_503_is_transient(self) -> None:
        err = _make_http_error(503)
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_504_is_transient(self) -> None:
        err = _make_http_error(504)
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_401_is_permanent(self) -> None:
        err = _make_http_error(401)
        assert classify_error(err, _ctx()) == ErrorCategory.PERMANENT

    def test_403_is_permanent(self) -> None:
        err = _make_http_error(403)
        assert classify_error(err, _ctx()) == ErrorCategory.PERMANENT


# ===================================================================
# Connection / timeout classification
# ===================================================================

class TestConnectionClassification:
    def test_connect_error_is_transient(self) -> None:
        request = httpx.Request("GET", "https://api.example.com")
        err = httpx.ConnectError("connection refused", request=request)
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_timeout_exception_is_transient(self) -> None:
        request = httpx.Request("GET", "https://api.example.com")
        err = httpx.ReadTimeout("timed out", request=request)
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_asyncio_timeout_is_transient(self) -> None:
        err = TimeoutError()
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT


# ===================================================================
# Domain error classification
# ===================================================================

class TestDomainClassification:
    def test_file_not_found_is_permanent(self) -> None:
        err = FileNotFoundError("no such file")
        assert classify_error(err, _ctx()) == ErrorCategory.PERMANENT

    def test_value_error_is_permanent(self) -> None:
        err = ValueError("invalid input")
        assert classify_error(err, _ctx()) == ErrorCategory.PERMANENT

    def test_budget_exceeded_is_permanent(self) -> None:
        err = BudgetExceededError(spent=5.0, limit=3.0)
        assert classify_error(err, _ctx()) == ErrorCategory.PERMANENT

    def test_circuit_open_is_transient(self) -> None:
        err = CircuitOpenError(engine="claude-code", retry_after=60)
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_generic_runtime_error_is_unknown(self) -> None:
        err = RuntimeError("something weird happened")
        assert classify_error(err, _ctx()) == ErrorCategory.UNKNOWN


# ===================================================================
# OOM & git-push heuristics
# ===================================================================

class TestRuntimeHeuristics:
    def test_oom_exit_code_137_is_transient(self) -> None:
        err = RuntimeError("Process exited with code 137")
        assert classify_error(err, _ctx()) == ErrorCategory.TRANSIENT

    def test_oom_killed_in_stderr_is_transient(self) -> None:
        err = RuntimeError("agent failed")
        ctx = _ctx(stderr_tail="out of memory: process killed")
        assert classify_error(err, ctx) == ErrorCategory.TRANSIENT

    def test_git_push_rejected_is_permanent(self) -> None:
        err = RuntimeError("push failed")
        ctx = _ctx(stderr_tail="! [rejected]        main -> main (non-fast-forward)")
        assert classify_error(err, ctx) == ErrorCategory.PERMANENT


# ===================================================================
# ErrorAction dataclass
# ===================================================================

class TestErrorAction:
    def test_retry_action_fields(self) -> None:
        action = ErrorAction(action="retry", delay=2.5)
        assert action.action == "retry"
        assert action.delay == 2.5
        assert action.issue_url is None

    def test_issue_created_action_fields(self) -> None:
        action = ErrorAction(
            action="issue_created",
            issue_url="https://github.com/org/repo/issues/42",
        )
        assert action.action == "issue_created"
        assert action.delay == 0.0
        assert action.issue_url == "https://github.com/org/repo/issues/42"


# ===================================================================
# Backoff
# ===================================================================

class TestBackoff:
    def test_backoff_increases_with_retry_count(self) -> None:
        # retry_count=0 -> base=1, retry_count=3 -> base=8
        # With jitter the value should always be >= base
        b0 = _backoff(0)
        assert 1.0 <= b0 <= 1.5  # base=1, jitter in [0, 0.5]

        b3 = _backoff(3)
        assert 8.0 <= b3 <= 12.0  # base=8, jitter in [0, 4.0]

    def test_backoff_caps_at_60(self) -> None:
        b = _backoff(10)  # 2**10 = 1024, capped to 60
        assert 60.0 <= b <= 90.0  # base=60, jitter in [0, 30]


# ===================================================================
# ErrorRouter.handle
# ===================================================================

class TestErrorRouterHandle:
    @pytest.mark.asyncio
    async def test_transient_with_retries_returns_retry(self) -> None:
        router = ErrorRouter()
        ctx = _ctx(retry_count=0, max_retries=3)
        err = _make_http_error(429)

        result = await router.handle(err, ctx)

        assert result.action == "retry"
        assert result.delay > 0
        assert result.issue_url is None

    @pytest.mark.asyncio
    async def test_transient_retries_exhausted_escalates(self) -> None:
        mock_creator = AsyncMock()
        mock_creator.create_or_update.return_value = "https://github.com/org/repo/issues/1"
        router = ErrorRouter(issue_creator=mock_creator)
        ctx = _ctx(retry_count=3, max_retries=3)
        err = _make_http_error(503)

        result = await router.handle(err, ctx)

        assert result.action == "issue_created"
        assert result.issue_url == "https://github.com/org/repo/issues/1"
        mock_creator.create_or_update.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_permanent_creates_issue(self) -> None:
        mock_creator = AsyncMock()
        mock_creator.create_or_update.return_value = "https://github.com/org/repo/issues/2"
        router = ErrorRouter(issue_creator=mock_creator)
        ctx = _ctx()
        err = ValueError("bad input")

        result = await router.handle(err, ctx)

        assert result.action == "issue_created"
        assert result.issue_url == "https://github.com/org/repo/issues/2"

    @pytest.mark.asyncio
    async def test_permanent_without_issue_creator(self) -> None:
        router = ErrorRouter(issue_creator=None)
        ctx = _ctx()
        err = FileNotFoundError("missing.py")

        result = await router.handle(err, ctx)

        assert result.action == "issue_created"
        assert result.issue_url is None

    @pytest.mark.asyncio
    async def test_issue_creator_failure_does_not_propagate(self) -> None:
        mock_creator = AsyncMock()
        mock_creator.create_or_update.side_effect = RuntimeError("GitHub down")
        router = ErrorRouter(issue_creator=mock_creator)
        ctx = _ctx()
        err = ValueError("bad input")

        result = await router.handle(err, ctx)

        # Should not raise, and should return action without URL
        assert result.action == "issue_created"
        assert result.issue_url is None

    @pytest.mark.asyncio
    async def test_unknown_error_escalates(self) -> None:
        mock_creator = AsyncMock()
        mock_creator.create_or_update.return_value = "https://github.com/org/repo/issues/3"
        router = ErrorRouter(issue_creator=mock_creator)
        ctx = _ctx()
        err = KeyError("wat")

        result = await router.handle(err, ctx)

        assert result.action == "issue_created"
        assert result.issue_url == "https://github.com/org/repo/issues/3"
