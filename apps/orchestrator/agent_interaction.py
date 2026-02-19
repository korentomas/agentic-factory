"""Agent-user interaction module for GitHub issue/PR comments.

Classifies incoming issues by type (bug, question, feature request, etc.)
and provides async helpers for posting clarification questions, results,
and answers back to GitHub issues.
"""

from __future__ import annotations

import os
import re
from enum import StrEnum

import httpx
import structlog

logger = structlog.get_logger()

_REPO = "korentomas/agentic-factory"

# ---------------------------------------------------------------------------
# Issue triage enum
# ---------------------------------------------------------------------------


class IssueTriage(StrEnum):
    """Classification of an incoming GitHub issue."""

    BUG = "bug"
    QUESTION = "question"
    USER_ERROR = "user_error"
    UNCLEAR = "unclear"
    FEATURE = "feature"


# ---------------------------------------------------------------------------
# Classification patterns
# ---------------------------------------------------------------------------

_FEATURE_PATTERNS: list[str] = [
    r"add\s+support\s+for",
    r"feature\s+request",
    r"would\s+be\s+(great|nice|good)",
    r"please\s+add",
    r"suggestion:",
]

_QUESTION_PATTERNS: list[str] = [
    r"how\s+(do|can|to)\s+i",
    r"what\s+(is|are|does)",
    r"where\s+(do|can|is)",
    r"is\s+it\s+possible",
    r"can\s+(i|you|we)",
]

_USER_ERROR_PATTERNS: list[str] = [
    r"401|403|unauthorized|forbidden",
    r"api.?key",
    r"credentials?",
    r"permission\s+denied",
    r"token\s+(expired|invalid|wrong)",
    r"env\s+var",
]

_BUG_PATTERNS: list[str] = [
    r"traceback",
    r"error|exception|crash",
    r"stack\s*trace",
    r"unexpected",
    r"broken",
    r"regression",
    r"bug",
    r"fails?\s+with",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_env(name: str, default: str = "") -> str:
    """Read an env var at call time (never at import time)."""
    return os.environ.get(name, default)


def _matches_any(text: str, patterns: list[str]) -> bool:
    """Return True if *text* matches any of the given regex patterns."""
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


# ---------------------------------------------------------------------------
# AgentInteraction
# ---------------------------------------------------------------------------


class AgentInteraction:
    """Handles agent-user interaction via GitHub issue and PR comments.

    Provides issue classification, clarification requests, result posting,
    and question answering with appropriate label management.

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
    # Classification
    # ------------------------------------------------------------------

    def classify_issue(self, title: str, body: str) -> IssueTriage:
        """Rule-based classification of a GitHub issue.

        Priority order: feature -> question (title only) -> user_error -> bug -> unclear.

        Args:
            title: The issue title.
            body: The issue body text.

        Returns:
            The classified :class:`IssueTriage` category.
        """
        title_lower = title.lower()
        body_lower = body.lower()
        combined = f"{title_lower} {body_lower}"

        # Feature patterns: title + body
        if _matches_any(combined, _FEATURE_PATTERNS):
            return IssueTriage.FEATURE

        # Question patterns: title only
        if _matches_any(title_lower, _QUESTION_PATTERNS):
            return IssueTriage.QUESTION

        # User error patterns: title + body
        if _matches_any(combined, _USER_ERROR_PATTERNS):
            return IssueTriage.USER_ERROR

        # Bug patterns: title + body
        if _matches_any(combined, _BUG_PATTERNS):
            return IssueTriage.BUG

        return IssueTriage.UNCLEAR

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------

    def _render_clarification(self, question: str, options: list[str]) -> str:
        """Render a Markdown clarification comment.

        Args:
            question: The question to ask the user.
            options: List of options for the user to choose from.

        Returns:
            Formatted Markdown string.
        """
        options_lines = "\n".join(f"- [ ] {opt}" for opt in options)
        return (
            "## Clarification Needed\n\n"
            "I'm working on this issue but need your input before proceeding.\n\n"
            f"**Question:** {question}\n\n"
            "**Options:**\n"
            f"{options_lines}\n"
            "- [ ] Other: reply with your preference\n\n"
            "Reply to this comment or check an option. "
            "I'll continue once I have your answer.\n\n"
            "---\n\n"
            "*Auto-generated by LailaTov. Reply to continue.*"
        )

    # ------------------------------------------------------------------
    # GitHub API helpers
    # ------------------------------------------------------------------

    async def _post_comment(self, issue_number: int, body: str) -> None:
        """Post a comment to a GitHub issue.

        Args:
            issue_number: The issue or PR number.
            body: The Markdown comment body.
        """
        token = self._get_token()
        url = (
            f"https://api.github.com/repos/{_REPO}"
            f"/issues/{issue_number}/comments"
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
            "agent_interaction.comment_posted",
            issue_number=issue_number,
        )

    async def _replace_label(
        self,
        issue_number: int,
        old_label: str,
        new_label: str,
    ) -> None:
        """Replace a label on a GitHub issue.

        Removes *old_label* (ignoring errors if it doesn't exist)
        then adds *new_label*.

        Args:
            issue_number: The issue or PR number.
            old_label: The label to remove.
            new_label: The label to add.
        """
        token = self._get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            # Remove old label (ignore if not present)
            delete_url = (
                f"https://api.github.com/repos/{_REPO}"
                f"/issues/{issue_number}/labels/{old_label}"
            )
            try:
                resp = await client.delete(delete_url, headers=headers)
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                logger.debug(
                    "agent_interaction.label_remove_skipped",
                    issue_number=issue_number,
                    label=old_label,
                )

            # Add new label
            add_url = (
                f"https://api.github.com/repos/{_REPO}"
                f"/issues/{issue_number}/labels"
            )
            resp = await client.post(
                add_url,
                json={"labels": [new_label]},
                headers=headers,
            )
            resp.raise_for_status()

        logger.info(
            "agent_interaction.label_replaced",
            issue_number=issue_number,
            old_label=old_label,
            new_label=new_label,
        )

    # ------------------------------------------------------------------
    # Public actions
    # ------------------------------------------------------------------

    async def ask_clarification(
        self,
        issue_number: int,
        question: str,
        options: list[str],
    ) -> None:
        """Post a clarification question and add the ``awaiting-reply`` label.

        Args:
            issue_number: The issue or PR number.
            question: The question to ask the user.
            options: List of options for the user to choose from.
        """
        body = self._render_clarification(question, options)
        await self._post_comment(issue_number, body)

        # Add awaiting-reply label
        token = self._get_token()
        label_url = (
            f"https://api.github.com/repos/{_REPO}"
            f"/issues/{issue_number}/labels"
        )
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                label_url,
                json={"labels": ["awaiting-reply"]},
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
            )
            resp.raise_for_status()

        logger.info(
            "agent_interaction.clarification_asked",
            issue_number=issue_number,
        )

    async def post_result(
        self,
        issue_number: int,
        result: str,
        pr_url: str | None = None,
    ) -> None:
        """Post a result summary to a GitHub issue.

        Args:
            issue_number: The issue or PR number.
            result: The result summary text.
            pr_url: Optional pull request URL to include.
        """
        body = f"## Result\n\n{result}"
        if pr_url:
            body += f"\n\n**Pull Request:** {pr_url}"
        body += "\n\n---\n\n*Auto-generated by LailaTov.*"

        await self._post_comment(issue_number, body)

        logger.info(
            "agent_interaction.result_posted",
            issue_number=issue_number,
            has_pr=pr_url is not None,
        )

    async def answer_question(
        self,
        issue_number: int,
        answer: str,
    ) -> None:
        """Post an answer to a question issue and relabel it.

        Posts the answer as a comment and replaces the ``bug`` label
        with ``question``.

        Args:
            issue_number: The issue or PR number.
            answer: The answer text.
        """
        body = f"## Answer\n\n{answer}\n\n---\n\n*Auto-generated by LailaTov.*"
        await self._post_comment(issue_number, body)
        await self._replace_label(issue_number, "bug", "question")

        logger.info(
            "agent_interaction.question_answered",
            issue_number=issue_number,
        )
