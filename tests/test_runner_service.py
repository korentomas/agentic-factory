"""Tests for apps.runner.main — the Agent Runner HTTP service."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from apps.runner.main import _execute_task, _tasks, app
from apps.runner.models import RunnerResult, RunnerTask, TaskState, TaskStatus


@pytest.fixture(autouse=True)
def _clear_tasks():
    """Clear task store between tests."""
    _tasks.clear()
    yield
    _tasks.clear()


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


# ── _execute_task tests ──────────────────────────────────────────────────────


class TestExecuteTask:
    """Tests for _execute_task background function."""

    def _make_state(self, task_id="t1"):
        task = RunnerTask(
            task_id=task_id,
            repo_url="https://github.com/org/repo",
            branch="agent/t1",
            base_branch="main",
            title="Fix bug",
            description="Fix the login bug",
        )
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
