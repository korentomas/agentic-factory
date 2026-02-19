"""Tests for apps.runner.main — the Agent Runner HTTP service."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.runner.main import (
    _execute_task,
    _tasks,
    app,
    audit_log,
    get_breaker,
    reset_breakers,
)
from apps.runner.models import RunnerResult, RunnerTask, TaskState, TaskStatus


@pytest.fixture(autouse=True)
def _clear_tasks():
    """Clear task store and breakers between tests."""
    _tasks.clear()
    audit_log.clear()
    reset_breakers()
    yield
    _tasks.clear()
    audit_log.clear()
    reset_breakers()


client = TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /health."""

    def test_health_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["active_tasks"] == 0
        assert "version" in data

    def test_health_counts_active_tasks(self):
        # Inject a running task
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        _tasks["t1"] = TaskState(task=task, status=TaskStatus.RUNNING)

        resp = client.get("/health")
        assert resp.json()["active_tasks"] == 1


class TestGetTask:
    """Tests for GET /tasks/{task_id}."""

    def test_not_found(self):
        resp = client.get("/tasks/nonexistent")
        assert resp.status_code == 404

    def test_pending_task(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        _tasks["t1"] = TaskState(task=task, status=TaskStatus.PENDING)

        resp = client.get("/tasks/t1")
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_completed_task_with_result(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        result = RunnerResult(
            task_id="t1",
            status="success",
            engine="claude-code",
            model="claude-sonnet-4-6",
            files_changed=["a.py"],
            cost_usd=0.10,
            num_turns=5,
            duration_ms=20000,
            commit_sha="abc123",
        )
        _tasks["t1"] = TaskState(
            task=task,
            status=TaskStatus.COMPLETE,
            result=result,
        )

        resp = client.get("/tasks/t1")
        data = resp.json()
        assert data["status"] == "complete"
        assert data["engine"] == "claude-code"
        assert data["cost_usd"] == 0.10
        assert data["files_changed"] == ["a.py"]
        assert data["commit_sha"] == "abc123"


class TestCancelTask:
    """Tests for POST /tasks/{task_id}/cancel."""

    def test_cancel_not_found(self):
        resp = client.post("/tasks/nonexistent/cancel")
        assert resp.status_code == 404

    def test_cancel_pending(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        _tasks["t1"] = TaskState(task=task, status=TaskStatus.PENDING)

        resp = client.post("/tasks/t1/cancel")
        assert resp.status_code == 200
        assert _tasks["t1"].status == TaskStatus.CANCELLED

    def test_cancel_sets_event(self):
        """Cancellation signals the cancel_event."""
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        state = TaskState(task=task, status=TaskStatus.RUNNING)
        _tasks["t1"] = state

        assert not state.cancel_event.is_set()
        resp = client.post("/tasks/t1/cancel")
        assert resp.status_code == 200
        assert state.cancel_event.is_set()

    def test_cancel_completed_fails(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        _tasks["t1"] = TaskState(task=task, status=TaskStatus.COMPLETE)

        resp = client.post("/tasks/t1/cancel")
        assert resp.status_code == 400

    def test_cancel_records_audit(self):
        """Cancellation creates an audit event."""
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        _tasks["t1"] = TaskState(task=task, status=TaskStatus.PENDING)

        client.post("/tasks/t1/cancel")
        events = audit_log.get_events("t1")
        assert any(e.action == "task.cancelled" for e in events)


class TestSubmitTask:
    """Tests for POST /tasks."""

    def test_submit_returns_202(self):
        resp = client.post("/tasks", json={
            "task_id": "gh-42",
            "repo_url": "https://github.com/org/repo",
            "branch": "agent/gh-42",
            "description": "Fix the login bug",
        })
        assert resp.status_code == 202
        data = resp.json()
        assert data["task_id"] == "gh-42"
        assert data["status"] == "pending"

    def test_submit_duplicate_409(self):
        task = RunnerTask(
            task_id="gh-42",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        _tasks["gh-42"] = TaskState(task=task)

        resp = client.post("/tasks", json={
            "task_id": "gh-42",
            "repo_url": "https://github.com/org/repo",
            "branch": "agent/gh-42",
            "description": "Duplicate",
        })
        assert resp.status_code == 409

    def test_submit_missing_fields(self):
        resp = client.post("/tasks", json={
            "task_id": "t1",
        })
        assert resp.status_code == 422

    def test_submit_records_audit(self):
        """Submission creates an audit event."""
        client.post("/tasks", json={
            "task_id": "t-audit",
            "repo_url": "https://github.com/org/repo",
            "branch": "b",
            "description": "desc",
        })
        events = audit_log.get_events("t-audit")
        assert any(e.action == "task.submitted" for e in events)

    def test_submit_with_sandbox_fields(self):
        """Sandbox fields are accepted in the request."""
        resp = client.post("/tasks", json={
            "task_id": "t-sandbox",
            "repo_url": "https://github.com/org/repo",
            "branch": "b",
            "description": "desc",
            "max_cost_usd": 5.0,
            "sandbox_mode": True,
            "sandbox_image": "custom/image:latest",
        })
        assert resp.status_code == 202
        state = _tasks["t-sandbox"]
        assert state.task.max_cost_usd == 5.0
        assert state.task.sandbox_mode is True
        assert state.task.sandbox_image == "custom/image:latest"

    def test_submit_stores_async_task_handle(self):
        """Background task handle is stored on TaskState."""
        client.post("/tasks", json={
            "task_id": "t-handle",
            "repo_url": "https://github.com/org/repo",
            "branch": "b",
            "description": "desc",
        })
        state = _tasks["t-handle"]
        assert state._async_task is not None


# ── _execute_task tests ──────────────────────────────────────────────────────


class TestExecuteTask:
    """Tests for _execute_task background function."""

    def _make_state(self, task_id="t1", **task_kwargs):
        defaults = {
            "task_id": task_id,
            "repo_url": "https://github.com/org/repo",
            "branch": "agent/t1",
            "base_branch": "main",
            "title": "Fix bug",
            "description": "Fix the login bug",
        }
        defaults.update(task_kwargs)
        task = RunnerTask(**defaults)
        state = TaskState(task=task)
        _tasks[task_id] = state
        return state

    @pytest.mark.asyncio
    async def test_execute_success_flow(self):
        state = self._make_state()
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t1",
            status="success",
            engine="claude-code",
            model="claude-sonnet-4-6",
            cost_usd=0.10,
            num_turns=5,
            duration_ms=15000,
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.commit_changes",
                new_callable=AsyncMock,
                return_value="abc123",
            ),
            patch(
                "apps.runner.main.push_changes",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "apps.runner.main.list_changed_files",
                new_callable=AsyncMock,
                return_value=["src/fix.py"],
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert state.status == TaskStatus.COMPLETE
        assert state.result is not None
        assert state.result.commit_sha == "abc123"
        assert state.result.files_changed == ["src/fix.py"]

    @pytest.mark.asyncio
    async def test_execute_passes_cancel_event_to_engine(self):
        """engine.run is called with cancel_event from TaskState."""
        state = self._make_state("t-ce")
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t-ce",
            status="failure",
            engine="claude-code",
            model="claude-sonnet-4-6",
            error_message="test",
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        # Verify cancel_event was passed as keyword argument
        mock_engine.run.assert_called_once()
        call_kwargs = mock_engine.run.call_args.kwargs
        assert "cancel_event" in call_kwargs
        assert call_kwargs["cancel_event"] is state.cancel_event

    @pytest.mark.asyncio
    async def test_execute_records_audit_trail(self):
        """Execute records start, engine_selected, and completed audit events."""
        state = self._make_state("t-audit")
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t-audit",
            status="failure",
            engine="claude-code",
            model="claude-sonnet-4-6",
            error_message="test",
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        events = audit_log.get_events("t-audit")
        actions = [e.action for e in events]
        assert "task.started" in actions
        assert "task.engine_selected" in actions
        assert "task.completed" in actions

    @pytest.mark.asyncio
    async def test_execute_engine_failure(self):
        state = self._make_state("t2")
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t2",
            status="failure",
            engine="claude-code",
            model="claude-sonnet-4-6",
            error_message="API key invalid",
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert state.status == TaskStatus.FAILED
        assert state.result is not None
        assert state.result.error_message == "API key invalid"

    @pytest.mark.asyncio
    async def test_execute_engine_failure_records_circuit_breaker(self):
        """Engine failure records a failure in the circuit breaker."""
        state = self._make_state("t-cb")
        mock_engine = AsyncMock()
        mock_engine.name = "test-engine"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t-cb",
            status="failure",
            engine="test-engine",
            model="test-model",
            error_message="fail",
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        breaker = get_breaker("test-engine")
        assert breaker._failure_count == 1

    @pytest.mark.asyncio
    async def test_execute_circuit_open_rejects_task(self):
        """When circuit is open, task fails immediately."""
        # Trip the circuit breaker
        breaker = get_breaker("claude-code")
        for _ in range(5):
            breaker.record_failure()
        assert breaker.state == "open"

        state = self._make_state("t-open")
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert state.status == TaskStatus.FAILED
        assert "Circuit open" in state.result.error_message
        mock_engine.run.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_budget_exceeded(self):
        """Task fails when cost exceeds max_cost_usd budget."""
        state = self._make_state("t-budget", max_cost_usd=0.05)
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t-budget",
            status="success",
            engine="claude-code",
            model="claude-sonnet-4-6",
            cost_usd=0.10,  # Exceeds 0.05 budget
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert state.status == TaskStatus.FAILED
        assert "budget exceeded" in state.result.error_message.lower()
        events = audit_log.get_events("t-budget")
        assert any(e.action == "task.budget_exceeded" for e in events)

    @pytest.mark.asyncio
    async def test_execute_workspace_creation_fails(self):
        state = self._make_state("t3")

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                side_effect=RuntimeError("clone failed"),
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert state.status == TaskStatus.FAILED
        assert state.result is not None
        assert "clone failed" in state.result.error_message

    @pytest.mark.asyncio
    async def test_execute_no_changes_to_commit(self):
        state = self._make_state("t4")
        mock_engine = AsyncMock()
        mock_engine.name = "aider"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t4",
            status="success",
            engine="aider",
            model="deepseek-chat",
            cost_usd=0.02,
            num_turns=3,
            duration_ms=8000,
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.commit_changes",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "apps.runner.main.list_changed_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "apps.runner.main.push_changes",
                new_callable=AsyncMock,
            ) as mock_push,
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert state.status == TaskStatus.COMPLETE
        assert state.result.commit_sha is None
        mock_push.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_keep_workspaces(self, monkeypatch):
        monkeypatch.setenv("LAILATOV_KEEP_WORKSPACES", "1")
        state = self._make_state("t5")
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t5",
            status="failure",
            engine="claude-code",
            model="claude-sonnet-4-6",
            error_message="test error",
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ) as mock_cleanup,
        ):
            await _execute_task(state)

        mock_cleanup.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_cancelled_error(self):
        """CancelledError results in CANCELLED status."""
        state = self._make_state("t-cancel")
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(side_effect=asyncio.CancelledError)

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert state.status == TaskStatus.CANCELLED
        assert state.result is not None
        assert state.result.status == "cancelled"
        assert state.result.error_message == "Task was cancelled"

    @pytest.mark.asyncio
    async def test_execute_failure_records_audit(self):
        """Exception during execution records a task.failed audit event."""
        state = self._make_state("t-fail-audit")

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        events = audit_log.get_events("t-fail-audit")
        actions = [e.action for e in events]
        assert "task.failed" in actions

    @pytest.mark.asyncio
    async def test_execute_success_records_circuit_breaker_success(self):
        """Successful execution resets circuit breaker failure count."""
        # Add a failure first
        breaker = get_breaker("claude-code")
        breaker.record_failure()
        assert breaker._failure_count == 1

        state = self._make_state("t-cb-ok")
        mock_engine = AsyncMock()
        mock_engine.name = "claude-code"
        mock_engine.run = AsyncMock(return_value=RunnerResult(
            task_id="t-cb-ok",
            status="success",
            engine="claude-code",
            model="claude-sonnet-4-6",
            cost_usd=0.05,
        ))

        with (
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
                return_value=mock_engine,
            ),
            patch(
                "apps.runner.main.commit_changes",
                new_callable=AsyncMock,
                return_value="sha",
            ),
            patch(
                "apps.runner.main.push_changes",
                new_callable=AsyncMock,
                return_value=True,
            ),
            patch(
                "apps.runner.main.list_changed_files",
                new_callable=AsyncMock,
                return_value=[],
            ),
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            await _execute_task(state)

        assert breaker._failure_count == 0
        assert breaker.state == "closed"


class TestGitHubAppTokenIntegration:
    """Tests for GitHub App token rotation in _execute_task."""

    @pytest.mark.asyncio
    async def test_uses_static_token_when_provided(self):
        """When github_token is provided, GitHub App token is NOT called."""
        task = RunnerTask(
            task_id="t-token",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        state = TaskState(task=task)
        _tasks["t-token"] = state

        with (
            patch(
                "apps.runner.main._get_github_app_token",
                new_callable=AsyncMock,
            ) as mock_app_token,
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ),
            patch(
                "apps.runner.main.select_engine",
            ) as mock_engine,
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            mock_adapter = AsyncMock()
            mock_adapter.name = "claude-code"
            mock_adapter.run = AsyncMock(
                return_value=RunnerResult(
                    task_id="t-token",
                    status="success",
                    engine="claude-code",
                    model="claude-sonnet-4-6",
                )
            )
            mock_engine.return_value = mock_adapter

            await _execute_task(state, github_token="static-token-abc")

        # Static token was passed, so no App token rotation
        mock_app_token.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_falls_back_to_github_app_token(self):
        """When no github_token, _get_github_app_token is called."""
        task = RunnerTask(
            task_id="t-app",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        state = TaskState(task=task)
        _tasks["t-app"] = state

        with (
            patch(
                "apps.runner.main._get_github_app_token",
                new_callable=AsyncMock,
                return_value="ghs_app_token_123",
            ) as mock_app_token,
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ) as mock_create,
            patch(
                "apps.runner.main.select_engine",
            ) as mock_engine,
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            mock_adapter = AsyncMock()
            mock_adapter.name = "claude-code"
            mock_adapter.run = AsyncMock(
                return_value=RunnerResult(
                    task_id="t-app",
                    status="success",
                    engine="claude-code",
                    model="claude-sonnet-4-6",
                )
            )
            mock_engine.return_value = mock_adapter

            await _execute_task(state, github_token=None)

        mock_app_token.assert_awaited_once()
        # Verify the app token was passed to create_workspace
        assert mock_create.call_args.kwargs["github_token"] == "ghs_app_token_123"

    @pytest.mark.asyncio
    async def test_github_app_token_none_proceeds_without_auth(self):
        """When GitHub App is not configured, clone proceeds without token."""
        task = RunnerTask(
            task_id="t-noapp",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        state = TaskState(task=task)
        _tasks["t-noapp"] = state

        with (
            patch(
                "apps.runner.main._get_github_app_token",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "apps.runner.main.create_workspace",
                new_callable=AsyncMock,
                return_value=Path("/tmp/fake"),
            ) as mock_create,
            patch(
                "apps.runner.main.select_engine",
            ) as mock_engine,
            patch(
                "apps.runner.main.cleanup_workspace",
                new_callable=AsyncMock,
            ),
        ):
            mock_adapter = AsyncMock()
            mock_adapter.name = "claude-code"
            mock_adapter.run = AsyncMock(
                return_value=RunnerResult(
                    task_id="t-noapp",
                    status="success",
                    engine="claude-code",
                    model="claude-sonnet-4-6",
                )
            )
            mock_engine.return_value = mock_adapter

            await _execute_task(state, github_token=None)

        assert mock_create.call_args.kwargs["github_token"] is None
