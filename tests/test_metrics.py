"""
Tests for the Prometheus /metrics endpoint.

Verifies that the endpoint:
- Returns HTTP 200
- Returns Prometheus text format (Content-Type: text/plain)
- Exposes the four expected metric families
- Records http_requests_total after a request is made
- Records notification_failures_total when a Slack post fails
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from fastapi.testclient import TestClient

# ── /metrics availability ─────────────────────────────────────────────────────


def test_metrics_endpoint_returns_200(client: TestClient) -> None:
    """GET /metrics returns HTTP 200."""
    response = client.get("/metrics")
    assert response.status_code == 200


def test_metrics_endpoint_content_type_is_prometheus_text(client: TestClient) -> None:
    """GET /metrics Content-Type header indicates Prometheus text exposition format."""
    response = client.get("/metrics")
    assert "text/plain" in response.headers["content-type"]


def test_metrics_endpoint_body_contains_help_lines(client: TestClient) -> None:
    """GET /metrics body contains at least one # HELP comment (Prometheus text format)."""
    response = client.get("/metrics")
    assert "# HELP" in response.text


# ── Expected metric families ──────────────────────────────────────────────────


def test_metrics_exposes_http_requests_total(client: TestClient) -> None:
    """GET /metrics exposes the http_requests_total counter family."""
    # Trigger a non-probe request so the metric has a sample.
    client.post(
        "/callbacks/agent-complete",
        json={
            "clickup_task_id": "test",
            "status": "success",
        },
    )
    response = client.get("/metrics")
    assert "http_requests_total" in response.text


def test_metrics_exposes_http_request_duration_seconds(client: TestClient) -> None:
    """GET /metrics exposes http_request_duration_seconds histogram."""
    client.post(
        "/callbacks/agent-complete",
        json={
            "clickup_task_id": "test",
            "status": "success",
        },
    )
    response = client.get("/metrics")
    assert "http_request_duration_seconds" in response.text


def test_metrics_exposes_webhook_dispatches_total(client: TestClient) -> None:
    """GET /metrics exposes webhook_dispatches_total counter."""
    response = client.get("/metrics")
    assert "webhook_dispatches_total" in response.text


def test_metrics_exposes_notification_failures_total(client: TestClient) -> None:
    """GET /metrics exposes notification_failures_total counter."""
    response = client.get("/metrics")
    assert "notification_failures_total" in response.text


# ── Metric instrumentation ────────────────────────────────────────────────────


def _get_metric_value(metrics_text: str, metric_name: str, labels: dict[str, str]) -> float:
    """Parse Prometheus text exposition format and return the value for a metric with labels."""
    label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    pattern = rf'^{re.escape(metric_name)}\{{{re.escape(label_str)}\}}\s+(\S+)'
    for line in metrics_text.splitlines():
        match = re.match(pattern, line)
        if match:
            return float(match.group(1))
    return 0.0


def test_http_requests_total_increments_after_callback_request(
    client: TestClient,
) -> None:
    """After POST /callbacks/agent-complete, http_requests_total includes a sample."""
    client.post(
        "/callbacks/agent-complete",
        json={
            "clickup_task_id": "test",
            "status": "success",
        },
    )

    response = client.get("/metrics")
    body = response.text

    # The metric line should contain labels for the callback request.
    assert 'method="POST"' in body
    assert 'path="/callbacks/agent-complete"' in body
    assert 'status_code="200"' in body


def test_health_and_metrics_excluded_from_prometheus_counters(
    client: TestClient,
) -> None:
    """Probe endpoints (/health, /metrics, /ready) should not appear in http_requests_total."""
    # Hit the probe endpoints
    client.get("/health")
    client.get("/metrics")
    client.get("/ready")

    response = client.get("/metrics")
    body = response.text

    # No http_requests_total line should have probe endpoint paths
    for line in body.splitlines():
        if line.startswith("http_requests_total{"):
            assert 'path="/health"' not in line
            assert 'path="/metrics"' not in line
            assert 'path="/ready"' not in line


def test_notification_failures_total_increments_on_slack_error(
    env_vars: dict[str, str],
) -> None:
    """notification_failures_total{target="slack"} increments when Slack POST fails."""
    from apps.orchestrator.main import app

    # Build a mock client that raises an HTTP error on POST.
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Internal Server Error"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "500",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with TestClient(app, raise_server_exceptions=False) as c:
            # Get baseline
            baseline = c.get("/metrics").text
            before = _get_metric_value(
                baseline, "notification_failures_total", {"target": "slack"}
            )

            c.post(
                "/callbacks/review-clean",
                json={
                    "pr_url": "https://github.com/org/repo/pull/1",
                    "pr_number": 1,
                    "branch": "agent/cu-abc123",
                    "risk_tier": "low",
                    "run_id": "12345",
                },
                headers={"X-Callback-Secret": env_vars["CALLBACK_SECRET"]},
            )

            after_text = c.get("/metrics").text
            after = _get_metric_value(
                after_text, "notification_failures_total", {"target": "slack"}
            )

    assert after > before, (
        f"notification_failures_total{{target='slack'}} should have incremented "
        f"(was {before}, now {after})"
    )


def test_notification_failures_total_increments_on_clickup_error(
    env_vars: dict[str, str],
) -> None:
    """notification_failures_total{target="clickup"} increments when ClickUp POST fails."""
    from apps.orchestrator.main import app

    mock_response = MagicMock()
    mock_response.status_code = 429
    mock_response.text = "Rate limited"
    mock_response.raise_for_status = MagicMock(
        side_effect=httpx.HTTPStatusError(
            "429",
            request=MagicMock(),
            response=mock_response,
        )
    )

    mock_client = AsyncMock()
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("httpx.AsyncClient", return_value=mock_client):
        with TestClient(app, raise_server_exceptions=False) as c:
            baseline = c.get("/metrics").text
            before = _get_metric_value(
                baseline, "notification_failures_total", {"target": "clickup"}
            )

            c.post(
                "/callbacks/review-clean",
                json={
                    "pr_url": "https://github.com/org/repo/pull/2",
                    "pr_number": 2,
                    "branch": "agent/cu-def456",
                    "risk_tier": "medium",
                    "run_id": "67890",
                },
                headers={"X-Callback-Secret": env_vars["CALLBACK_SECRET"]},
            )

            after_text = c.get("/metrics").text
            after = _get_metric_value(
                after_text, "notification_failures_total", {"target": "clickup"}
            )

    assert after > before, (
        f"notification_failures_total{{target='clickup'}} should have incremented "
        f"(was {before}, now {after})"
    )
