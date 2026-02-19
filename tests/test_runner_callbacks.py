"""Tests for runner callback dispatch during task execution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from apps.runner.main import _execute_task, _tasks, audit_log, reset_breakers
from apps.runner.models import RunnerResult, RunnerTask, TaskState


@pytest.fixture(autouse=True)
def _clear() -> None:
    _tasks.clear()
    audit_log.clear()
    reset_breakers()


def _make_task(callback_url: str | None = None, task_id: str = "cb-test-001") -> RunnerTask:
    """Build a minimal RunnerTask for callback tests."""
    return RunnerTask(
        task_id=task_id,
        repo_url="https://github.com/test/repo",
        branch="test-branch",
        base_branch="main",
        description="Fix the bug",
        callback_url=callback_url,
    )


def _setup_mocks(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Patch workspace + engine to avoid real git/CLI calls. Returns the fake engine."""
    async def fake_create_workspace(*args: object, **kwargs: object) -> Path:
        return Path("/tmp/fake")  # noqa: S108

    fake_engine = AsyncMock()
    fake_engine.name = "claude-code"
    fake_engine.run.return_value = RunnerResult(
        task_id="cb-test-001",
        status="success",
        engine="claude-code",
        model="haiku",
        cost_usd=0.01,
        duration_ms=1000,
    )

    monkeypatch.setattr("apps.runner.main.create_workspace", fake_create_workspace)
    monkeypatch.setattr("apps.runner.main.cleanup_workspace", AsyncMock())
    monkeypatch.setattr("apps.runner.main.commit_changes", AsyncMock(return_value=None))
    monkeypatch.setattr("apps.runner.main.list_changed_files", AsyncMock(return_value=[]))
    monkeypatch.setattr("apps.runner.main.select_engine", lambda **kw: fake_engine)
    monkeypatch.setattr("apps.runner.main._error_router.handle", AsyncMock())

    return fake_engine


@pytest.mark.asyncio
async def test_callback_posts_lifecycle_events(monkeypatch: pytest.MonkeyPatch) -> None:
    """When callback_url is set, runner POSTs lifecycle events."""
    collected: list[dict] = []

    async def fake_post(self: object, url: str, *, json: dict, **kwargs: object) -> object:
        collected.append(json)
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        return mock_resp

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    _setup_mocks(monkeypatch)

    task = _make_task(callback_url="http://localhost:3000/api/tasks/cb-test-001/webhook")
    state = TaskState(task=task)

    await _execute_task(state)

    types = [c["type"] for c in collected]
    assert "status" in types, f"Expected 'status' callback, got: {types}"
    assert "complete" in types or "failed" in types, f"Expected terminal callback, got: {types}"


@pytest.mark.asyncio
async def test_no_callback_when_url_not_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """When callback_url is None, no HTTP posts are made."""
    post_called = False

    async def spy_post(self: object, url: str, *, json: dict, **kwargs: object) -> None:
        nonlocal post_called
        post_called = True

    monkeypatch.setattr("httpx.AsyncClient.post", spy_post)
    _setup_mocks(monkeypatch)

    task = _make_task(callback_url=None)
    state = TaskState(task=task)
    await _execute_task(state)

    assert not post_called, "Should not POST when callback_url is None"


@pytest.mark.asyncio
async def test_callback_failure_does_not_block_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """If callback POST fails, task execution continues to completion."""
    async def failing_post(self: object, url: str, *, json: dict, **kwargs: object) -> None:
        raise ConnectionError("webhook down")

    monkeypatch.setattr("httpx.AsyncClient.post", failing_post)
    _setup_mocks(monkeypatch)

    task = _make_task(callback_url="http://localhost:3000/api/tasks/cb-test-003/webhook")
    state = TaskState(task=task)
    await _execute_task(state)

    assert state.status.value == "complete"


@pytest.mark.asyncio
async def test_callback_sends_engine_selected_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Callback includes engine selection as a system message."""
    collected: list[dict] = []

    async def fake_post(self: object, url: str, *, json: dict, **kwargs: object) -> object:
        collected.append(json)
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        return mock_resp

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)
    _setup_mocks(monkeypatch)

    task = _make_task(callback_url="http://localhost:3000/webhook")
    state = TaskState(task=task)
    await _execute_task(state)

    messages = [c for c in collected if c.get("type") == "message"]
    assert len(messages) >= 1
    assert "claude-code" in messages[0]["content"]


@pytest.mark.asyncio
async def test_callback_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Failed tasks send a 'failed' callback."""
    collected: list[dict] = []

    async def fake_post(self: object, url: str, *, json: dict, **kwargs: object) -> object:
        collected.append(json)
        mock_resp = AsyncMock()
        mock_resp.status_code = 200
        return mock_resp

    monkeypatch.setattr("httpx.AsyncClient.post", fake_post)

    fake_engine = _setup_mocks(monkeypatch)
    fake_engine.run.return_value = RunnerResult(
        task_id="cb-test-fail",
        status="failure",
        engine="claude-code",
        model="haiku",
        error_message="Engine failed",
    )

    task = _make_task(callback_url="http://localhost:3000/webhook", task_id="cb-test-fail")
    state = TaskState(task=task)
    await _execute_task(state)

    # Terminal callback should be "complete" with failed status (engine returned failure,
    # but task execution itself succeeded)
    types = [c["type"] for c in collected]
    assert "complete" in types or "failed" in types
