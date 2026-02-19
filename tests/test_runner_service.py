"""Tests for apps.runner.main — the Agent Runner HTTP service."""

import pytest
from fastapi.testclient import TestClient

from apps.runner.main import _tasks, app
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
