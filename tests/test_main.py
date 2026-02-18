"""
Tests for apps.orchestrator.main — FastAPI application entry point.

Covers: health endpoint, 404 handler, request logging middleware,
request ID middleware, docs endpoint configuration, and structured
logging setup.
"""

from __future__ import annotations

import importlib
import uuid
from unittest.mock import patch

import pytest
import structlog
from fastapi.testclient import TestClient

# ── Health endpoint ──────────────────────────────────────────────────────────


def test_health_returns_200_with_service_info(client: TestClient) -> None:
    """GET /health returns 200 with status and service name."""
    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "agent-factory-orchestrator"


# ── 404 handler ──────────────────────────────────────────────────────────────


def test_nonexistent_route_returns_404_with_error_body(client: TestClient) -> None:
    """GET on a route that does not exist returns 404 with structured error."""
    response = client.get("/nonexistent")

    assert response.status_code == 404
    assert response.json() == {"error": "not_found"}


# ── Request logging middleware ───────────────────────────────────────────────


def test_middleware_binds_structlog_contextvars(client: TestClient) -> None:
    """The request logging middleware binds method and path to structlog contextvars."""
    captured: dict[str, object] = {}

    original_bind = structlog.contextvars.bind_contextvars

    def spy_bind(**kwargs: object) -> None:
        captured.update(kwargs)
        original_bind(**kwargs)

    with patch.object(structlog.contextvars, "bind_contextvars", side_effect=spy_bind):
        client.get("/health")

    assert captured["method"] == "GET"
    assert captured["path"] == "/health"
    assert "client" in captured


def test_middleware_clears_contextvars_before_binding(client: TestClient) -> None:
    """The middleware clears contextvars at the start of each request to avoid leaking."""
    clear_called = False

    original_clear = structlog.contextvars.clear_contextvars

    def spy_clear() -> None:
        nonlocal clear_called
        clear_called = True
        original_clear()

    with patch.object(structlog.contextvars, "clear_contextvars", side_effect=spy_clear):
        client.get("/health")

    assert clear_called, "clear_contextvars should be called before binding new context"


# ── Request ID middleware ─────────────────────────────────────────────────────


def test_health_response_includes_x_request_id_header(client: TestClient) -> None:
    """GET /health response includes an X-Request-ID header."""
    response = client.get("/health")

    assert response.status_code == 200
    assert "x-request-id" in response.headers


def test_generated_request_id_is_valid_uuid4(client: TestClient) -> None:
    """When no X-Request-ID is sent, the middleware generates a valid UUID4."""
    response = client.get("/health")

    request_id = response.headers["x-request-id"]
    parsed = uuid.UUID(request_id)
    assert parsed.version == 4


def test_client_provided_request_id_is_preserved(client: TestClient) -> None:
    """When the client sends X-Request-ID, the same value is echoed in the response."""
    custom_id = "my-trace-abc123"
    response = client.get("/health", headers={"X-Request-ID": custom_id})

    assert response.headers["x-request-id"] == custom_id


def test_different_requests_get_different_request_ids(client: TestClient) -> None:
    """Each request without a client-supplied ID receives a unique request ID."""
    r1 = client.get("/health")
    r2 = client.get("/health")

    assert r1.headers["x-request-id"] != r2.headers["x-request-id"]


def test_middleware_binds_request_id_to_structlog_context(client: TestClient) -> None:
    """The middleware binds request_id to the structlog contextvars."""
    captured: dict[str, object] = {}

    original_bind = structlog.contextvars.bind_contextvars

    def spy_bind(**kwargs: object) -> None:
        captured.update(kwargs)
        original_bind(**kwargs)

    with patch.object(structlog.contextvars, "bind_contextvars", side_effect=spy_bind):
        client.get("/health")

    assert "request_id" in captured
    # The bound value must be a valid UUID4 string.
    parsed = uuid.UUID(str(captured["request_id"]))
    assert parsed.version == 4


def test_middleware_binds_client_request_id_to_structlog_context(
    client: TestClient,
) -> None:
    """When the client provides X-Request-ID, that value is bound to structlog context."""
    captured: dict[str, object] = {}
    custom_id = "client-trace-xyz"

    original_bind = structlog.contextvars.bind_contextvars

    def spy_bind(**kwargs: object) -> None:
        captured.update(kwargs)
        original_bind(**kwargs)

    with patch.object(structlog.contextvars, "bind_contextvars", side_effect=spy_bind):
        client.get("/health", headers={"X-Request-ID": custom_id})

    assert captured["request_id"] == custom_id


# ── Docs endpoint configuration ──────────────────────────────────────────────


def test_docs_disabled_by_default(client: TestClient) -> None:
    """When DOCS_ENABLED is not set (defaults to false), /docs returns 404."""
    response = client.get("/docs")

    assert response.status_code == 404


def test_docs_enabled_when_env_var_set(
    monkeypatch: pytest.MonkeyPatch,
    env_vars: dict[str, str],
) -> None:
    """When DOCS_ENABLED=true, the /docs endpoint is available and returns 200."""

    monkeypatch.setenv("DOCS_ENABLED", "true")

    # The app object is created at module level using os.getenv, so we must
    # reload the module to pick up the new DOCS_ENABLED value.
    import apps.orchestrator.main as main_module

    importlib.reload(main_module)

    try:
        with TestClient(main_module.app, raise_server_exceptions=False) as docs_client:
            response = docs_client.get("/docs")
            assert response.status_code == 200
    finally:
        # Restore the module to its default state so other tests are unaffected.
        monkeypatch.delenv("DOCS_ENABLED")
        importlib.reload(main_module)


# ── _configure_logging ───────────────────────────────────────────────────────


def test_configure_logging_runs_without_error_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """_configure_logging() succeeds with default env (no LOG_LEVEL, no LOG_PRETTY)."""
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    monkeypatch.delenv("LOG_PRETTY", raising=False)

    from apps.orchestrator.main import _configure_logging

    # Should not raise any exception.
    _configure_logging()

    # Verify structlog is usable after configuration.
    log = structlog.get_logger("test")
    assert log is not None


def test_configure_logging_respects_log_pretty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When LOG_PRETTY=true, _configure_logging uses ConsoleRenderer."""
    monkeypatch.setenv("LOG_PRETTY", "true")

    from apps.orchestrator.main import _configure_logging

    _configure_logging()

    # Inspect the structlog configuration to verify ConsoleRenderer is used.
    config = structlog.get_config()
    processors = config["processors"]
    renderer = processors[-1]
    assert isinstance(renderer, structlog.dev.ConsoleRenderer)


def test_configure_logging_uses_json_renderer_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When LOG_PRETTY is not set, _configure_logging uses JSONRenderer."""
    monkeypatch.delenv("LOG_PRETTY", raising=False)

    from apps.orchestrator.main import _configure_logging

    _configure_logging()

    config = structlog.get_config()
    processors = config["processors"]
    renderer = processors[-1]
    assert isinstance(renderer, structlog.processors.JSONRenderer)
