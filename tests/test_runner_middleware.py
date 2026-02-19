"""Tests for apps.runner.middleware — API key authentication."""

import pytest
from fastapi.testclient import TestClient

from apps.runner.main import _tasks, app
from apps.runner.models import RunnerTask, TaskState, TaskStatus


@pytest.fixture(autouse=True)
def _clear_tasks():
    """Clear task store between tests."""
    _tasks.clear()
    yield
    _tasks.clear()


client = TestClient(app)


class TestAPIKeyMiddleware:
    """Tests for APIKeyMiddleware."""

    def test_open_mode_no_key_configured(self, monkeypatch):
        """When RUNNER_API_KEY is not set, all requests are allowed."""
        monkeypatch.delenv("RUNNER_API_KEY", raising=False)
        resp = client.get("/tasks/nonexistent")
        # Should reach the endpoint (404 = endpoint logic, not auth)
        assert resp.status_code == 404

    def test_health_always_public(self, monkeypatch):
        """Health endpoint is accessible even with auth enabled."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"

    def test_docs_always_public(self, monkeypatch):
        """OpenAPI docs are accessible even with auth enabled."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        resp = client.get("/openapi.json")
        assert resp.status_code == 200

    def test_missing_auth_header_returns_401(self, monkeypatch):
        """Requests without Authorization header get 401."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        resp = client.get("/tasks/some-id")
        assert resp.status_code == 401
        assert "Missing" in resp.json()["error"]

    def test_invalid_token_returns_401(self, monkeypatch):
        """Requests with wrong token get 401."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        resp = client.get(
            "/tasks/some-id",
            headers={"Authorization": "Bearer wrong-key"},
        )
        assert resp.status_code == 401
        assert "Invalid" in resp.json()["error"]

    def test_valid_token_passes_through(self, monkeypatch):
        """Requests with correct token reach the endpoint."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        # 404 = endpoint reached (no task exists), not auth failure
        resp = client.get(
            "/tasks/some-id",
            headers={"Authorization": "Bearer secret-key-123"},
        )
        assert resp.status_code == 404

    def test_non_bearer_scheme_returns_401(self, monkeypatch):
        """Non-Bearer auth schemes are rejected."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        resp = client.get(
            "/tasks/some-id",
            headers={"Authorization": "Basic dXNlcjpwYXNz"},
        )
        assert resp.status_code == 401

    def test_submit_task_requires_auth(self, monkeypatch):
        """POST /tasks is protected."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        resp = client.post("/tasks", json={
            "task_id": "t1",
            "repo_url": "https://github.com/org/repo",
            "branch": "b",
            "description": "desc",
        })
        assert resp.status_code == 401

    def test_submit_task_with_auth(self, monkeypatch):
        """POST /tasks works with valid auth."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        resp = client.post(
            "/tasks",
            json={
                "task_id": "t1",
                "repo_url": "https://github.com/org/repo",
                "branch": "b",
                "description": "desc",
            },
            headers={"Authorization": "Bearer secret-key-123"},
        )
        assert resp.status_code == 202

    def test_cancel_requires_auth(self, monkeypatch):
        """POST /tasks/{id}/cancel is protected."""
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key-123")
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        _tasks["t1"] = TaskState(task=task, status=TaskStatus.RUNNING)

        resp = client.post("/tasks/t1/cancel")
        assert resp.status_code == 401
