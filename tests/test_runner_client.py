"""Tests for apps.orchestrator.runner_client — orchestrator → runner bridge."""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from apps.orchestrator.models import AgentTask
from apps.orchestrator.providers import PipelineStage
from apps.orchestrator.runner_client import RunnerClient, RunnerError

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_task(**overrides):
    defaults = {
        "task_id": "abc123",
        "task_details": {"name": "Fix login bug", "description": "The login page crashes"},
    }
    defaults.update(overrides)
    return AgentTask.from_clickup_payload(**defaults)


def _mock_response(status_code=200, json_data=None):
    """Build an httpx.Response with a dummy request (needed for raise_for_status)."""
    request = httpx.Request("POST", "http://localhost:8001/tasks")
    return httpx.Response(status_code, json=json_data or {}, request=request)


# ── RunnerClient basics ──────────────────────────────────────────────────────


class TestRunnerClientConfig:
    """Tests for RunnerClient configuration."""

    def test_default_base_url(self, monkeypatch):
        monkeypatch.delenv("RUNNER_URL", raising=False)
        client = RunnerClient()
        assert client.base_url == "http://localhost:8001"

    def test_env_base_url(self, monkeypatch):
        monkeypatch.setenv("RUNNER_URL", "http://runner:9000")
        client = RunnerClient()
        assert client.base_url == "http://runner:9000"

    def test_constructor_base_url(self, monkeypatch):
        monkeypatch.setenv("RUNNER_URL", "http://from-env:8001")
        client = RunnerClient(base_url="http://explicit:8001")
        assert client.base_url == "http://explicit:8001"


# ── submit_task ──────────────────────────────────────────────────────────────


class TestSubmitTask:
    """Tests for RunnerClient.submit_task."""

    @pytest.mark.asyncio
    async def test_submit_success(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "org/repo")
        monkeypatch.setenv("GITHUB_APP_TOKEN", "ghp_test")
        monkeypatch.delenv("RUNNER_API_KEY", raising=False)

        mock_post = AsyncMock(return_value=_mock_response(
            202, {"task_id": "cu-abc123", "status": "pending"}
        ))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            task = _make_task()
            result = await client.submit_task(task)

        assert result["task_id"] == "cu-abc123"
        assert result["status"] == "pending"

        # Verify the URL and payload
        call_args = mock_post.call_args
        assert "http://localhost:8001/tasks" in call_args.args[0]
        payload = call_args.kwargs["json"]
        assert payload["task_id"] == "cu-abc123"
        assert payload["repo_url"] == "https://github.com/org/repo"
        assert payload["branch"] == "agent/cu-abc123"
        assert payload["title"] == "Fix login bug"

    @pytest.mark.asyncio
    async def test_submit_with_api_key(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "org/repo")
        monkeypatch.setenv("GITHUB_APP_TOKEN", "ghp_test")
        monkeypatch.setenv("RUNNER_API_KEY", "secret-key")

        mock_post = AsyncMock(return_value=_mock_response(
            202, {"task_id": "cu-abc123", "status": "pending"}
        ))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            task = _make_task()
            await client.submit_task(task)

        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer secret-key"

    @pytest.mark.asyncio
    async def test_submit_http_error(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "org/repo")
        monkeypatch.setenv("GITHUB_APP_TOKEN", "ghp_test")

        error_resp = httpx.Response(
            409,
            json={"detail": "Task already exists"},
            request=httpx.Request("POST", "http://localhost:8001/tasks"),
        )
        mock_post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "409", request=error_resp.request, response=error_resp
        ))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            task = _make_task()
            with pytest.raises(RunnerError, match="HTTP 409"):
                await client.submit_task(task)

    @pytest.mark.asyncio
    async def test_submit_connection_error(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "org/repo")
        monkeypatch.setenv("GITHUB_APP_TOKEN", "ghp_test")

        mock_post = AsyncMock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            task = _make_task()
            with pytest.raises(RunnerError, match="unreachable"):
                await client.submit_task(task)

    @pytest.mark.asyncio
    async def test_submit_with_stage(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "org/repo")
        monkeypatch.setenv("GITHUB_APP_TOKEN", "ghp_test")

        mock_post = AsyncMock(return_value=_mock_response(
            202, {"task_id": "cu-abc123", "status": "pending"}
        ))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            task = _make_task()
            result = await client.submit_task(task, stage=PipelineStage.TRIAGE)

        assert result["task_id"] == "cu-abc123"

    @pytest.mark.asyncio
    async def test_submit_with_custom_token(self, monkeypatch):
        monkeypatch.setenv("GITHUB_REPO", "org/repo")
        monkeypatch.delenv("RUNNER_API_KEY", raising=False)

        mock_post = AsyncMock(return_value=_mock_response(
            202, {"task_id": "cu-abc123", "status": "pending"}
        ))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.post = mock_post
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            task = _make_task()
            await client.submit_task(task, github_token="custom-token")

        payload = mock_post.call_args.kwargs["json"]
        assert payload["github_token"] == "custom-token"


# ── get_task_status ──────────────────────────────────────────────────────────


class TestGetTaskStatus:
    """Tests for RunnerClient.get_task_status."""

    @pytest.mark.asyncio
    async def test_get_status_success(self, monkeypatch):
        monkeypatch.delenv("RUNNER_API_KEY", raising=False)

        mock_get = AsyncMock(return_value=_mock_response(200, {
            "task_id": "cu-abc123",
            "status": "complete",
            "engine": "claude-code",
            "cost_usd": 0.15,
        }))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            result = await client.get_task_status("cu-abc123")

        assert result["status"] == "complete"
        assert result["cost_usd"] == 0.15

    @pytest.mark.asyncio
    async def test_get_status_not_found(self, monkeypatch):
        monkeypatch.delenv("RUNNER_API_KEY", raising=False)

        error_resp = httpx.Response(
            404,
            json={"detail": "Not found"},
            request=httpx.Request("GET", "http://localhost:8001/tasks/missing"),
        )
        mock_get = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=error_resp.request, response=error_resp
        ))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            with pytest.raises(RunnerError, match="HTTP 404"):
                await client.get_task_status("missing")

    @pytest.mark.asyncio
    async def test_get_status_with_api_key(self, monkeypatch):
        monkeypatch.setenv("RUNNER_API_KEY", "my-key")

        mock_get = AsyncMock(return_value=_mock_response(200, {
            "task_id": "cu-abc123",
            "status": "running",
        }))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            await client.get_task_status("cu-abc123")

        headers = mock_get.call_args.kwargs.get("headers", {})
        assert headers.get("Authorization") == "Bearer my-key"


# ── health_check ─────────────────────────────────────────────────────────────


class TestHealthCheck:
    """Tests for RunnerClient.health_check."""

    @pytest.mark.asyncio
    async def test_healthy(self):
        mock_get = AsyncMock(return_value=_mock_response(200, {"status": "ok"}))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            assert await client.health_check() is True

    @pytest.mark.asyncio
    async def test_unhealthy_status(self):
        mock_get = AsyncMock(return_value=_mock_response(503))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            assert await client.health_check() is False

    @pytest.mark.asyncio
    async def test_unreachable(self):
        mock_get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

        with patch("apps.orchestrator.runner_client.httpx.AsyncClient") as mock_cls:
            mock_client = AsyncMock()
            mock_client.get = mock_get
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = mock_client

            client = RunnerClient()
            assert await client.health_check() is False
