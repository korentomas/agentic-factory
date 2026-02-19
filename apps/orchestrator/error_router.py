"""Central error classification and dispatch.

Classifies errors into transient vs permanent categories,
computes retry backoff, and escalates unrecoverable failures
to the issue tracker.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

import httpx
import structlog

from apps.runner.budget import BudgetExceededError
from apps.runner.circuit_breaker import CircuitOpenError

logger = structlog.get_logger()


# ---------------------------------------------------------------------------
# Enums & value objects
# ---------------------------------------------------------------------------

class ErrorCategory(StrEnum):
    """Broad classification of an error for retry decisions."""

    TRANSIENT = "transient"
    PERMANENT = "permanent"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ErrorContext:
    """Rich context attached to every error for classification and logging."""

    component: str
    task_id: str | None = None
    engine: str | None = None
    model: str | None = None
    stage: str | None = None
    user_tier: str | None = None
    execution_path: str | None = None
    stderr_tail: str = ""
    stdout_tail: str = ""
    retry_count: int = 0
    max_retries: int = 3


@dataclass(frozen=True)
class ErrorAction:
    """Instruction returned by the router after handling an error."""

    action: str  # "retry" or "issue_created"
    delay: float = 0.0
    issue_url: str | None = None


# ---------------------------------------------------------------------------
# Protocol for the issue creator dependency
# ---------------------------------------------------------------------------

class IssueCreator(Protocol):
    """Minimal interface for creating/updating bug-report issues."""

    async def create_or_update(
        self,
        error: Exception,
        context: ErrorContext,
        category: ErrorCategory,
    ) -> str:
        """Return the URL of the created or updated issue."""
        ...  # pragma: no cover


# ---------------------------------------------------------------------------
# Classification logic
# ---------------------------------------------------------------------------

_TRANSIENT_HTTP_CODES = frozenset({429, 502, 503, 504})
_PERMANENT_HTTP_CODES = frozenset({401, 403})


def classify_error(error: Exception, context: ErrorContext) -> ErrorCategory:
    """Determine whether *error* is transient, permanent, or unknown.

    Classification rules (checked in order):
    - httpx HTTP status errors: 429/5xx gateway -> transient; 401/403 -> permanent
    - httpx connectivity / timeout errors -> transient
    - TimeoutError (asyncio.TimeoutError) -> transient
    - CircuitOpenError -> transient (engine temporarily unavailable)
    - BudgetExceededError -> permanent (cost ceiling hit)
    - FileNotFoundError, ValueError -> permanent
    - RuntimeError with OOM signals (exit 137, "killed") -> transient
    - RuntimeError with git-push "rejected" -> permanent
    - Everything else -> unknown
    """
    # --- httpx HTTP status errors ---
    if isinstance(error, httpx.HTTPStatusError):
        code = error.response.status_code
        if code in _TRANSIENT_HTTP_CODES:
            return ErrorCategory.TRANSIENT
        if code in _PERMANENT_HTTP_CODES:
            return ErrorCategory.PERMANENT
        return ErrorCategory.UNKNOWN

    # --- httpx connectivity / timeout ---
    if isinstance(error, (httpx.ConnectError, httpx.TimeoutException)):
        return ErrorCategory.TRANSIENT

    # --- stdlib timeout ---
    if isinstance(error, TimeoutError):
        return ErrorCategory.TRANSIENT

    # --- domain errors ---
    if isinstance(error, CircuitOpenError):
        return ErrorCategory.TRANSIENT

    if isinstance(error, BudgetExceededError):
        return ErrorCategory.PERMANENT

    if isinstance(error, FileNotFoundError):
        return ErrorCategory.PERMANENT

    if isinstance(error, ValueError):
        return ErrorCategory.PERMANENT

    # --- RuntimeError heuristics ---
    if isinstance(error, RuntimeError):
        msg = str(error).lower()
        stderr = context.stderr_tail.lower()
        if "137" in msg or "killed" in stderr:
            return ErrorCategory.TRANSIENT
        if "rejected" in stderr:
            return ErrorCategory.PERMANENT
        return ErrorCategory.UNKNOWN

    return ErrorCategory.UNKNOWN


# ---------------------------------------------------------------------------
# Backoff helper
# ---------------------------------------------------------------------------

def _backoff(retry_count: int) -> float:
    """Exponential backoff with jitter, capped at 60 s."""
    base: float = min(2 ** retry_count, 60)
    jitter = random.uniform(0, base * 0.5)  # noqa: S311
    return base + jitter


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

class ErrorRouter:
    """Centralized error handler: classify -> retry-or-escalate.

    Args:
        issue_creator: Optional dependency that files bug-report issues.
                       Can be ``None`` for testing or when issue creation
                       is not wired up yet.
    """

    def __init__(self, issue_creator: IssueCreator | None = None) -> None:
        self._issue_creator = issue_creator

    async def handle(
        self,
        error: Exception,
        context: ErrorContext,
    ) -> ErrorAction:
        """Decide what to do with *error* given *context*.

        Returns an :class:`ErrorAction` describing whether to retry
        (with a delay) or that an issue was created for human follow-up.
        """
        category = classify_error(error, context)

        logger.info(
            "error_router.classified",
            category=category.value,
            error_type=type(error).__name__,
            component=context.component,
            task_id=context.task_id,
            retry_count=context.retry_count,
        )

        # Transient errors with retries remaining -> retry with backoff
        if category == ErrorCategory.TRANSIENT and context.retry_count < context.max_retries:
            delay = _backoff(context.retry_count)
            logger.info(
                "error_router.retry",
                delay=delay,
                retry_count=context.retry_count,
                max_retries=context.max_retries,
            )
            return ErrorAction(action="retry", delay=delay)

        # Transient errors with retries exhausted -> escalate to permanent
        if category == ErrorCategory.TRANSIENT:
            logger.warning(
                "error_router.retries_exhausted",
                retry_count=context.retry_count,
                max_retries=context.max_retries,
            )
            category = ErrorCategory.PERMANENT

        # Permanent / unknown -> create or update an issue
        return await self._escalate(error, context, category)

    async def _escalate(
        self,
        error: Exception,
        context: ErrorContext,
        category: ErrorCategory,
    ) -> ErrorAction:
        """Create/update an issue for permanent or unknown errors."""
        issue_url: str | None = None

        if self._issue_creator is not None:
            try:
                issue_url = await self._issue_creator.create_or_update(
                    error, context, category,
                )
                logger.info("error_router.issue_created", issue_url=issue_url)
            except Exception as exc:
                # Issue-creation failures must not break the caller
                logger.error(
                    "error_router.issue_creation_failed",
                    error=str(exc),
                )
        else:
            logger.warning("error_router.no_issue_creator")

        return ErrorAction(action="issue_created", issue_url=issue_url)
