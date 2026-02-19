"""Circuit breaker for engine reliability.

Prevents repeated calls to failing engines/providers.
State machine: closed -> open -> half_open -> closed.
"""

from __future__ import annotations

import time
from typing import Literal

import structlog

logger = structlog.get_logger()


class CircuitOpenError(Exception):
    """Raised when a request is rejected due to an open circuit."""

    def __init__(self, engine: str, retry_after: float) -> None:
        self.engine = engine
        self.retry_after = retry_after
        super().__init__(
            f"Circuit open for engine {engine!r}. "
            f"Retry after {retry_after:.0f}s."
        )


class CircuitBreaker:
    """Per-engine circuit breaker.

    Args:
        failure_threshold: Number of consecutive failures before opening.
        recovery_timeout:  Seconds to wait before trying half-open probe.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 300,
        name: str = "",
    ) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.name = name
        self._failure_count = 0
        self._opened_at: float | None = None
        self._state: Literal["closed", "open", "half_open"] = "closed"

    @property
    def state(self) -> Literal["closed", "open", "half_open"]:
        """Current circuit state, accounting for recovery timeout."""
        if self._state == "open" and self._opened_at is not None:
            elapsed = time.monotonic() - self._opened_at
            if elapsed >= self.recovery_timeout:
                self._state = "half_open"
        return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        s = self.state
        if s == "closed":
            return True
        if s == "half_open":
            return True
        return False

    def record_success(self) -> None:
        """Record a successful execution."""
        if self._state == "half_open":
            logger.info("circuit_breaker.closed", name=self.name)
        self._failure_count = 0
        self._state = "closed"
        self._opened_at = None

    def record_failure(self) -> None:
        """Record a failed execution."""
        self._failure_count += 1
        if self._state == "half_open":
            self._state = "open"
            self._opened_at = time.monotonic()
            logger.warning("circuit_breaker.reopened", name=self.name)
        elif self._failure_count >= self.failure_threshold:
            self._state = "open"
            self._opened_at = time.monotonic()
            logger.warning(
                "circuit_breaker.opened",
                name=self.name,
                failures=self._failure_count,
            )
