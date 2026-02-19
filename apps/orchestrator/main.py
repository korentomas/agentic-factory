"""
AgentFactory Orchestrator — FastAPI application entry point.

Responsibilities:
- Receive and verify ClickUp webhooks (routed to routers/clickup.py)
- Receive GitHub Actions callbacks (routed to routers/callbacks.py)
- Emit structured JSON logs for Cloud Logging ingestion
- Expose Prometheus metrics at /metrics
- Validate risk-policy.json schema at startup
"""

from __future__ import annotations

import fnmatch
import json
import logging
import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

from apps import __version__
from apps.orchestrator import metrics as _metrics
from apps.orchestrator.routers import callbacks, clickup


# ── Structured logging ─────────────────────────────────────────────────────────
def _configure_logging() -> None:
    """Configure structlog. Reads env vars at call time, not import time."""
    log_level = os.getenv("LOG_LEVEL", "info").upper()
    log_pretty = os.getenv("LOG_PRETTY", "false").lower() == "true"

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if log_pretty
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level, logging.INFO)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
    )


_configure_logging()
logger = structlog.get_logger(__name__)

VALID_TIERS = {"high", "medium", "low"}


# ── Risk policy validation ────────────────────────────────────────────────────
def _validate_risk_policy(policy_path: str = "risk-policy.json") -> list[str]:
    """Validate risk-policy.json schema and return a list of errors (empty if valid).

    Checks:
    - File exists and is valid JSON
    - ``riskTierRules`` key exists with only valid tier names (high/medium/low)
    - ``mergePolicy`` keys match ``riskTierRules`` keys exactly
    - All glob patterns are syntactically valid
    """
    errors: list[str] = []
    path = Path(policy_path)

    if not path.exists():
        return [f"risk-policy.json not found at {policy_path}"]

    try:
        policy = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        return [f"risk-policy.json is not valid JSON: {exc}"]

    if not isinstance(policy, dict):
        return ["risk-policy.json root must be a JSON object"]

    # Validate riskTierRules
    tier_rules = policy.get("riskTierRules")
    if tier_rules is None:
        errors.append("Missing required key: riskTierRules")
    elif not isinstance(tier_rules, dict):
        errors.append("riskTierRules must be a JSON object")
    else:
        invalid_tiers = set(tier_rules.keys()) - VALID_TIERS
        if invalid_tiers:
            errors.append(
                f"Invalid tier names in riskTierRules: {sorted(invalid_tiers)}"
            )

        # Validate glob patterns
        for tier, patterns in tier_rules.items():
            if not isinstance(patterns, list):
                errors.append(
                    f"riskTierRules.{tier} must be an array of glob patterns"
                )
                continue
            for pattern in patterns:
                if not isinstance(pattern, str) or not pattern.strip():
                    errors.append(
                        f"riskTierRules.{tier} contains invalid pattern: {pattern!r}"
                    )
                    continue
                # Validate the glob is syntactically usable
                try:
                    fnmatch.translate(pattern)
                except Exception as exc:  # noqa: BLE001
                    errors.append(
                        f"riskTierRules.{tier} pattern {pattern!r} is invalid: {exc}"
                    )

    # Validate mergePolicy
    merge_policy = policy.get("mergePolicy")
    if merge_policy is None:
        errors.append("Missing required key: mergePolicy")
    elif not isinstance(merge_policy, dict):
        errors.append("mergePolicy must be a JSON object")
    elif tier_rules and isinstance(tier_rules, dict):
        tier_keys = set(tier_rules.keys())
        merge_keys = set(merge_policy.keys())
        if tier_keys != merge_keys:
            missing_from_merge = tier_keys - merge_keys
            extra_in_merge = merge_keys - tier_keys
            if missing_from_merge:
                errors.append(
                    f"mergePolicy missing tiers: {sorted(missing_from_merge)}"
                )
            if extra_in_merge:
                errors.append(
                    f"mergePolicy has extra tiers not in riskTierRules: "
                    f"{sorted(extra_in_merge)}"
                )

    return errors


# ── Lifespan: startup validation ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Validate configuration at startup. Log clearly what's missing.
    Cloud Run will restart the container on failure — we want clear logs.
    """
    # Validate risk-policy.json schema (used by CI risk gate, not the orchestrator)
    policy_errors = _validate_risk_policy()
    if policy_errors:
        for err in policy_errors:
            logger.warning("risk_policy_validation_error", error=err)
        logger.warning(
            "risk_policy_invalid",
            error_count=len(policy_errors),
            impact="Risk policy gate in CI may behave unexpectedly. Fix risk-policy.json.",
        )
    else:
        logger.info("risk_policy_validated")

    required: list[str] = [
        "CLICKUP_WEBHOOK_SECRET",
        "CLICKUP_API_TOKEN",
        "GITHUB_APP_TOKEN",
        "GITHUB_REPO",
        "ORCHESTRATOR_URL",
        "CALLBACK_SECRET",
    ]
    optional_for_notifications: list[str] = [
        "SLACK_WEBHOOK_URL",
    ]

    missing_required = [v for v in required if not os.getenv(v)]
    missing_optional = [v for v in optional_for_notifications if not os.getenv(v)]

    if missing_required:
        logger.warning(
            "startup_missing_required_vars",
            missing=missing_required,
            impact="Webhook verification or dispatch will fail until these are set.",
        )
    if missing_optional:
        logger.warning(
            "startup_missing_optional_vars",
            missing=missing_optional,
            impact="Slack notifications will be silently skipped.",
        )

    logger.info(
        "orchestrator_starting",
        github_repo=os.getenv("GITHUB_REPO", "(not set)"),
        environment=os.getenv("ENVIRONMENT", "production"),
        log_level=os.getenv("LOG_LEVEL", "info").upper(),
    )

    yield

    logger.info("orchestrator_stopping")


# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="AgentFactory Orchestrator",
    description=(
        "Autonomous AI code factory — ClickUp tickets become reviewed, "
        "tested GitHub PRs automatically."
    ),
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs" if os.getenv("DOCS_ENABLED", "false").lower() == "true" else None,
    redoc_url=None,
    openapi_url=(
        "/openapi.json"
        if os.getenv("DOCS_ENABLED", "false").lower() == "true"
        else None
    ),
)


# ── Request logging middleware ─────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Log every request with method, path, status, duration, and request ID.

    Propagates the client-supplied ``X-Request-ID`` header when present;
    otherwise generates a fresh UUID4. The request ID is bound to the
    structlog context so all logs within the request carry ``request_id``.

    Also records Prometheus metrics:
    - http_requests_total (method, path, status_code)
    - http_request_duration_seconds (method, path)
    """
    start = time.monotonic()

    request_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else "unknown",
    )

    response: Response = await call_next(request)

    duration_s = time.monotonic() - start
    duration_ms = round(duration_s * 1000, 2)
    logger.info("http_request", status=response.status_code, duration_ms=duration_ms)

    path = request.url.path
    if path not in ("/metrics", "/health", "/ready"):
        _metrics.HTTP_REQUESTS_TOTAL.labels(
            method=request.method,
            path=path,
            status_code=str(response.status_code),
        ).inc()
        _metrics.HTTP_REQUEST_DURATION_SECONDS.labels(
            method=request.method,
            path=path,
        ).observe(duration_s)

    response.headers["X-Request-ID"] = request_id
    return response


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(clickup.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(callbacks.router, prefix="/callbacks", tags=["callbacks"])


# ── Metrics ────────────────────────────────────────────────────────────────────
app.mount("/metrics", _metrics.make_metrics_app())


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"], include_in_schema=False)
async def health() -> dict[str, str]:
    """
    Liveness probe for Cloud Run and load balancers.
    Returns 200 with no dependency checks — always fast.
    """
    return {"status": "ok", "service": "agent-factory-orchestrator", "version": __version__}


@app.get("/ready", tags=["system"], include_in_schema=False)
async def ready() -> JSONResponse:
    """
    Readiness probe for Cloud Run startup probes.

    Checks that required env vars are set and non-empty. Returns 503 with the
    list of missing vars if any are absent, or 200 when the service is ready to
    accept traffic.

    Required vars (CLICKUP_WEBHOOK_SECRET is optional — its absence disables
    HMAC verification, which is acceptable for development):
    - CLICKUP_API_TOKEN
    - SLACK_WEBHOOK_URL
    """
    required: list[str] = ["CLICKUP_API_TOKEN", "SLACK_WEBHOOK_URL"]
    missing = [var for var in required if not os.getenv(var)]

    if missing:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready", "missing": missing},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready"},
    )


# ── Error handlers ─────────────────────────────────────────────────────────────
@app.exception_handler(404)
async def not_found(_request: Request, _exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "not_found"},
    )


@app.exception_handler(500)
async def server_error(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "internal_server_error"},
    )


# ── CLI entry point ────────────────────────────────────────────────────────────
def cli_main() -> None:
    """Entry point registered in pyproject.toml as `agent-factory` command."""
    import uvicorn  # noqa: PLC0415

    uvicorn.run(
        "apps.orchestrator.main:app",
        host="0.0.0.0",  # noqa: S104 — intentional for Cloud Run
        port=int(os.getenv("PORT", "8080")),
        reload=os.getenv("ENVIRONMENT") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
        access_log=False,  # We log requests ourselves in the middleware
    )


if __name__ == "__main__":
    cli_main()
