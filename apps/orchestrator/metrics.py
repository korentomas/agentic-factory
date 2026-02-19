"""
Prometheus metrics for AgentFactory Orchestrator.

Defines and registers all metrics on a custom CollectorRegistry so that
test runs in the same process do not conflict with one another.  The registry
is *not* the global default — it is passed explicitly to ``make_asgi_app()``.

Metrics exposed:
  - http_requests_total          counter  (method, path, status_code)
  - http_request_duration_seconds histogram (method, path)
  - webhook_dispatches_total     counter  (source)
  - notification_failures_total  counter  (target)
  - model_invocations_total      counter  (provider, model, stage, risk_tier)
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client import make_asgi_app as _make_asgi_app
from starlette.types import ASGIApp

# ── Isolated registry ──────────────────────────────────────────────────────────
# Using a custom registry (instead of the prometheus_client global REGISTRY)
# avoids duplicate-registration errors when the FastAPI app module is reloaded
# during tests.
REGISTRY: CollectorRegistry = CollectorRegistry()

# ── Metrics ───────────────────────────────────────────────────────────────────
HTTP_REQUESTS_TOTAL: Counter = Counter(
    "http_requests_total",
    "Total number of HTTP requests received.",
    ["method", "path", "status_code"],
    registry=REGISTRY,
)

HTTP_REQUEST_DURATION_SECONDS: Histogram = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ["method", "path"],
    registry=REGISTRY,
)

WEBHOOK_DISPATCHES_TOTAL: Counter = Counter(
    "webhook_dispatches_total",
    "Total number of webhook dispatches sent to GitHub Actions.",
    ["source"],
    registry=REGISTRY,
)

NOTIFICATION_FAILURES_TOTAL: Counter = Counter(
    "notification_failures_total",
    "Total number of failed notification attempts.",
    ["target"],
    registry=REGISTRY,
)

MODEL_INVOCATIONS_TOTAL: Counter = Counter(
    "model_invocations_total",
    "Total model invocations across pipeline stages.",
    ["provider", "model", "stage", "risk_tier"],
    registry=REGISTRY,
)


def make_metrics_app() -> ASGIApp:
    """Return an ASGI app that serves Prometheus metrics in text format.

    Mount this at ``/metrics`` via ``app.mount("/metrics", make_metrics_app())``.
    """
    return _make_asgi_app(registry=REGISTRY)
