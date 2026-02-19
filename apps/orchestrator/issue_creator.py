"""GitHub issue auto-creation with deduplication.

Creates or updates GitHub issues for errors that the error router
escalates.  Uses SHA-256 hashing of the root cause signature to
avoid opening duplicate issues for the same failure mode.
"""

from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime

import httpx
import structlog

from apps.orchestrator.error_router import ErrorCategory, ErrorContext

logger = structlog.get_logger()

_REPO = "korentomas/agentic-factory"

_SUGGESTED_FIXES: dict[str, str] = {
    "FileNotFoundError": (
        "CLI binary not found. Install the required engine CLI."
    ),
    "BudgetExceededError": (
        "Task cost exceeded the configured budget limit. "
        "Increase `max_cost_usd` or optimize the prompt."
    ),
    "CircuitOpenError": (
        "Engine circuit breaker is open due to repeated failures. "
        "Wait for the recovery timeout or check the engine's health."
    ),
}

_DEFAULT_FIX = "Investigate the error details below."


def _get_env(name: str, default: str = "") -> str:
    """Read an env var at call time (never at import time)."""
    return os.environ.get(name, default)


class IssueCreator:
    """Creates or updates GitHub issues for unrecoverable errors.

    Deduplicates by hashing the root-cause signature so repeated
    occurrences of the same failure append comments to an existing
    issue rather than opening new ones.

    Args:
        github_token: Optional explicit token.  Falls back to
                      ``GITHUB_TOKEN`` then ``GH_TOKEN`` env vars.
    """

    def __init__(self, github_token: str | None = None) -> None:
        self._explicit_token = github_token

    # ------------------------------------------------------------------
    # Token resolution
    # ------------------------------------------------------------------

    def _get_token(self) -> str:
        """Resolve the GitHub token.

        Priority: constructor arg > GITHUB_TOKEN env > GH_TOKEN env.

        Raises:
            ValueError: If no token is available.
        """
        token = (
            self._explicit_token
            or _get_env("GITHUB_TOKEN")
            or _get_env("GH_TOKEN")
        )
        if not token:
            raise ValueError(
                "No GitHub token available. "
                "Set GITHUB_TOKEN or GH_TOKEN, or pass github_token=."
            )
        return token

    # ------------------------------------------------------------------
    # Dedup hash
    # ------------------------------------------------------------------

    def _compute_hash(self, error: Exception, context: ErrorContext) -> str:
        """SHA-256 hash of the root-cause signature, truncated to 12 hex chars.

        The signature is ``{component}:{error_type}:{engine or 'none'}``.
        This means the same class of error from the same component/engine
        always maps to one issue, regardless of the error message.
        """
        error_type = type(error).__name__
        engine = context.engine or "none"
        raw = f"{context.component}:{error_type}:{engine}"
        return hashlib.sha256(raw.encode()).hexdigest()[:12]

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_title(self, error: Exception, context: ErrorContext) -> str:
        """Build a concise issue title.

        Format: ``[{component}] {ErrorType}: {message[:80]}``
        """
        error_type = type(error).__name__
        message = str(error)[:80]
        return f"[{context.component}] {error_type}: {message}"

    def _render_body(
        self,
        error: Exception,
        context: ErrorContext,
        category: ErrorCategory,
        dedup_hash: str,
    ) -> str:
        """Render a Markdown issue body with diagnostics."""
        error_type = type(error).__name__
        timestamp = datetime.now(UTC).isoformat()
        suggested_fix = _SUGGESTED_FIXES.get(error_type, _DEFAULT_FIX)

        stderr_section = ""
        if context.stderr_tail:
            tail = context.stderr_tail[-500:]
            stderr_section = (
                "\n## Stderr\n\n"
                "<details>\n<summary>Last 500 chars</summary>\n\n"
                f"```\n{tail}\n```\n\n"
                "</details>\n"
            )

        return (
            "## Diagnostics\n\n"
            "| Field | Value |\n"
            "| --- | --- |\n"
            f"| Component | {context.component} |\n"
            f"| Task ID | {context.task_id or 'N/A'} |\n"
            f"| Engine | {context.engine or 'N/A'} |\n"
            f"| Model | {context.model or 'N/A'} |\n"
            f"| Stage | {context.stage or 'N/A'} |\n"
            f"| Category | {category.value} |\n"
            f"| Timestamp | {timestamp} |\n"
            f"| Dedup Hash | `{dedup_hash}` |\n"
            "\n"
            "## Error\n\n"
            f"**Type:** `{error_type}`\n\n"
            f"**Message:** {error}\n"
            f"{stderr_section}\n"
            "## Suggested Fix\n\n"
            f"{suggested_fix}\n"
        )

    # ------------------------------------------------------------------
    # Labels
    # ------------------------------------------------------------------

    def _get_labels(self, category: ErrorCategory) -> list[str]:
        """Return labels for the issue."""
        return ["bug", "auto-reported", "ai-agent", category.value]

    # ------------------------------------------------------------------
    # GitHub API helpers
    # ------------------------------------------------------------------

    async def _find_duplicate(self, dedup_hash: str) -> dict | None:
        """Search GitHub for an open issue with the same dedup hash.

        Uses the Issues search API:
        ``repo:{_REPO} is:issue is:open label:auto-reported {dedup_hash}``
        """
        token = self._get_token()
        query = f"repo:{_REPO} is:issue is:open label:auto-reported {dedup_hash}"
        url = "https://api.github.com/search/issues"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                params={"q": query},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            data = resp.json()

        items = data.get("items", [])
        if items:
            logger.info(
                "issue_creator.duplicate_found",
                issue_url=items[0].get("html_url"),
                dedup_hash=dedup_hash,
            )
            return items[0]
        return None

    async def _create_issue(
        self,
        title: str,
        body: str,
        labels: list[str],
    ) -> dict:
        """Create a new GitHub issue via the REST API."""
        token = self._get_token()
        url = f"https://api.github.com/repos/{_REPO}/issues"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"title": title, "body": body, "labels": labels},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()
            return resp.json()

    async def _append_comment(
        self,
        existing: dict,
        error: Exception,
        context: ErrorContext,
    ) -> None:
        """Add a recurring-occurrence comment to an existing issue."""
        token = self._get_token()
        issue_number = existing["number"]
        url = (
            f"https://api.github.com/repos/{_REPO}"
            f"/issues/{issue_number}/comments"
        )
        timestamp = datetime.now(UTC).isoformat()
        body = (
            "## Recurring Occurrence\n\n"
            f"**Timestamp:** {timestamp}\n\n"
            f"**Component:** {context.component}\n\n"
            f"**Task ID:** {context.task_id or 'N/A'}\n\n"
            f"**Engine:** {context.engine or 'N/A'}\n\n"
            f"**Error:** {error}\n"
        )

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                url,
                json={"body": body},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()

        logger.info(
            "issue_creator.comment_appended",
            issue_number=issue_number,
        )

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def create_or_update(
        self,
        error: Exception,
        context: ErrorContext,
        category: ErrorCategory,
    ) -> str:
        """Create a new issue or update an existing one.

        Returns the issue URL, or ``""`` if issue creation fails.
        This method never raises — issue tracking must not crash the caller.
        """
        try:
            dedup_hash = self._compute_hash(error, context)

            existing = await self._find_duplicate(dedup_hash)
            if existing is not None:
                await self._append_comment(existing, error, context)
                return existing.get("html_url", "")

            title = self._render_title(error, context)
            body = self._render_body(error, context, category, dedup_hash)
            labels = self._get_labels(category)

            issue = await self._create_issue(title, body, labels)
            url = issue.get("html_url", "")
            logger.info("issue_creator.created", issue_url=url)
            return url

        except Exception as exc:
            logger.error(
                "issue_creator.failed",
                error=str(exc),
                error_type=type(exc).__name__,
                component=context.component,
                task_id=context.task_id,
            )
            return ""
