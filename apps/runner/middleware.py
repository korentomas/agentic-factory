"""Authentication middleware for the Agent Runner.

Validates Bearer token against RUNNER_API_KEY env var.
If RUNNER_API_KEY is not set, all requests are allowed (open mode).
Health and docs endpoints are always public.
"""

from __future__ import annotations

import os
from collections.abc import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = structlog.get_logger()

# Paths that never require authentication.
PUBLIC_PATHS = frozenset({"/health", "/docs", "/openapi.json"})


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Validate Bearer token against RUNNER_API_KEY env var.

    If RUNNER_API_KEY is not set, all requests are allowed (open mode).
    Health and docs endpoints are always public.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Check authorization on protected endpoints."""
        api_key = _get_env("RUNNER_API_KEY")

        # Open mode: no key configured, allow everything
        if not api_key:
            return await call_next(request)

        # Public paths: always accessible
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Validate bearer token
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            logger.warning("auth.missing", path=request.url.path)
            return JSONResponse(
                {"error": "Missing or invalid Authorization header"},
                status_code=401,
            )

        token = auth_header[7:]  # Strip "Bearer "
        if token != api_key:
            logger.warning("auth.invalid", path=request.url.path)
            return JSONResponse(
                {"error": "Invalid API key"},
                status_code=401,
            )

        return await call_next(request)
