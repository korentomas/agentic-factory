"""
AgentFactory Orchestrator — FastAPI application entry point.

Responsibilities:
- Receive and verify ClickUp webhooks (routed to routers/clickup.py)
- Receive GitHub Actions callbacks (routed to routers/callbacks.py)
- Emit structured JSON logs for Cloud Logging ingestion
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, Response, status
from fastapi.responses import JSONResponse

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


# ── Lifespan: startup validation ───────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Validate configuration at startup. Log clearly what's missing.
    Cloud Run will restart the container on failure — we want clear logs.
    """
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

    duration_ms = round((time.monotonic() - start) * 1000, 2)
    logger.info("http_request", status=response.status_code, duration_ms=duration_ms)

    response.headers["X-Request-ID"] = request_id
    return response


# ── Routers ────────────────────────────────────────────────────────────────────
app.include_router(clickup.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(callbacks.router, prefix="/callbacks", tags=["callbacks"])


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"], include_in_schema=False)
async def health() -> dict[str, str]:
    """
    Liveness probe for Cloud Run and load balancers.
    Returns 200 with no dependency checks — always fast.
    """
    return {"status": "ok", "service": "agent-factory-orchestrator"}


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
