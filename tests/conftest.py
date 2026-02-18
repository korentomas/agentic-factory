"""
Shared pytest fixtures for AgentFactory tests.

Provides:
- FastAPI TestClient configured with mocked env vars
- Common env var fixtures
- httpx response mocking helpers
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env_vars(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set standard env vars for testing. Returns the dict for inspection."""
    defaults: dict[str, str] = {
        "CLICKUP_WEBHOOK_SECRET": "test-webhook-secret",
        "CLICKUP_API_TOKEN": "test-clickup-token",
        "GITHUB_APP_TOKEN": "test-github-token",
        "GITHUB_REPO": "test-org/test-repo",
        "ORCHESTRATOR_URL": "https://test.example.com",
        "CALLBACK_SECRET": "test-callback-secret",
        "SLACK_WEBHOOK_URL": "https://hooks.slack.com/test",
        "SLACK_CHANNEL": "test-channel",
        "ENVIRONMENT": "test",
    }
    for key, value in defaults.items():
        monkeypatch.setenv(key, value)
    return defaults


@pytest.fixture()
def client(env_vars: dict[str, str]) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with env vars pre-configured."""
    from apps.orchestrator.main import app

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


@pytest.fixture()
def mock_httpx_post() -> Generator[AsyncMock, None, None]:
    """Mock httpx.AsyncClient for outbound POST requests."""
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    mock_response.text = "ok"
    mock_response.raise_for_status = MagicMock()

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        yield mock_client
