"""Tests for the GitHub issue auto-creator with deduplication."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from apps.orchestrator.error_router import ErrorCategory, ErrorContext
from apps.orchestrator.issue_creator import IssueCreator
from apps.runner.budget import BudgetExceededError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ctx(**overrides: object) -> ErrorContext:
    """Convenience: create an ErrorContext with sensible defaults."""
    defaults: dict[str, object] = {
        "component": "runner",
        "task_id": "task-42",
        "engine": "claude-code",
        "model": "claude-opus-4",
        "stage": "write",
    }
    defaults.update(overrides)
    return ErrorContext(**defaults)  # type: ignore[arg-type]


def _creator() -> IssueCreator:
    """Build an IssueCreator with an explicit token (avoids env lookup)."""
    return IssueCreator(github_token="ghp_test_token")


# ===================================================================
# TestDedupHash
# ===================================================================

class TestDedupHash:
    """Deduplication hash: same root cause -> same hash."""

    def test_same_root_cause_same_hash(self) -> None:
        """Same error type + same component + same engine -> same hash."""
        creator = _creator()
        ctx = _ctx()
        err1 = FileNotFoundError("claude not found")
        err2 = FileNotFoundError("totally different message")
        assert creator._compute_hash(err1, ctx) == creator._compute_hash(err2, ctx)

    def test_different_component_different_hash(self) -> None:
        """Different component -> different hash."""
        creator = _creator()
        err = FileNotFoundError("missing")
        ctx_a = _ctx(component="runner")
        ctx_b = _ctx(component="orchestrator")
        assert creator._compute_hash(err, ctx_a) != creator._compute_hash(err, ctx_b)

    def test_different_error_type_different_hash(self) -> None:
        """Different error type -> different hash."""
        creator = _creator()
        ctx = _ctx()
        err_a = FileNotFoundError("missing")
        err_b = ValueError("bad value")
        assert creator._compute_hash(err_a, ctx) != creator._compute_hash(err_b, ctx)

    def test_hash_is_12_chars_long(self) -> None:
        """Dedup hash should be exactly 12 hex characters."""
        creator = _creator()
        h = creator._compute_hash(FileNotFoundError("x"), _ctx())
        assert len(h) == 12

    def test_hash_is_valid_hex(self) -> None:
        """Dedup hash should consist of valid hexadecimal characters."""
        creator = _creator()
        h = creator._compute_hash(FileNotFoundError("x"), _ctx())
        int(h, 16)  # raises ValueError if not valid hex


# ===================================================================
# TestRenderTitle
# ===================================================================

class TestRenderTitle:
    """Issue title rendering."""

    def test_title_includes_error_type(self) -> None:
        creator = _creator()
        err = ValueError("bad input")
        title = creator._render_title(err, _ctx())
        assert "ValueError" in title

    def test_title_includes_component(self) -> None:
        creator = _creator()
        err = ValueError("bad input")
        title = creator._render_title(err, _ctx(component="orchestrator"))
        assert "[orchestrator]" in title


# ===================================================================
# TestRenderBody
# ===================================================================

class TestRenderBody:
    """Issue body rendering."""

    def test_body_contains_diagnostics_table(self) -> None:
        creator = _creator()
        ctx = _ctx(
            component="runner",
            task_id="task-99",
            engine="aider",
            model="gpt-4o",
            stage="review",
        )
        err = ValueError("oops")
        body = creator._render_body(err, ctx, ErrorCategory.PERMANENT, "abc123def456")

        assert "| Component | runner |" in body
        assert "| Task ID | task-99 |" in body
        assert "| Engine | aider |" in body
        assert "| Model | gpt-4o |" in body
        assert "| Stage | review |" in body
        assert "| Category | permanent |" in body
        assert "| Dedup Hash | `abc123def456` |" in body

    def test_body_contains_stderr_when_present(self) -> None:
        creator = _creator()
        ctx = _ctx(stderr_tail="fatal: permission denied")
        err = RuntimeError("boom")
        body = creator._render_body(err, ctx, ErrorCategory.UNKNOWN, "aaa111bbb222")

        assert "## Stderr" in body
        assert "fatal: permission denied" in body
        assert "<details>" in body

    def test_body_contains_suggested_fix_for_known_errors(self) -> None:
        creator = _creator()
        ctx = _ctx()
        err = BudgetExceededError(spent=5.0, limit=3.0)
        body = creator._render_body(err, ctx, ErrorCategory.PERMANENT, "aaa111bbb222")

        assert "## Suggested Fix" in body
        assert "max_cost_usd" in body


# ===================================================================
# TestIssueLabels
# ===================================================================

class TestIssueLabels:
    """Label generation by error category."""

    def test_permanent_labels(self) -> None:
        creator = _creator()
        labels = creator._get_labels(ErrorCategory.PERMANENT)
        assert labels == ["bug", "auto-reported", "ai-agent", "permanent"]

    def test_transient_labels(self) -> None:
        creator = _creator()
        labels = creator._get_labels(ErrorCategory.TRANSIENT)
        assert "transient" in labels

    def test_unknown_labels(self) -> None:
        creator = _creator()
        labels = creator._get_labels(ErrorCategory.UNKNOWN)
        assert "unknown" in labels


# ===================================================================
# TestCreateOrUpdate
# ===================================================================

class TestCreateOrUpdate:
    """Integration tests for the main entry point (mocked HTTP)."""

    @pytest.mark.asyncio
    async def test_creates_new_issue_when_no_duplicate(self) -> None:
        """When no duplicate exists, create a fresh issue and return its URL."""
        creator = _creator()
        expected_url = "https://github.com/korentomas/agentic-factory/issues/42"

        with (
            patch.object(
                creator, "_find_duplicate", new_callable=AsyncMock, return_value=None,
            ) as mock_find,
            patch.object(
                creator,
                "_create_issue",
                new_callable=AsyncMock,
                return_value={"html_url": expected_url, "number": 42},
            ) as mock_create,
        ):
            url = await creator.create_or_update(
                FileNotFoundError("claude not found"),
                _ctx(),
                ErrorCategory.PERMANENT,
            )

        assert url == expected_url
        mock_find.assert_awaited_once()
        mock_create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_appends_comment_when_duplicate_exists(self) -> None:
        """When a duplicate is found, append a comment instead of creating."""
        creator = _creator()
        existing_issue = {
            "html_url": "https://github.com/korentomas/agentic-factory/issues/7",
            "number": 7,
        }

        with (
            patch.object(
                creator,
                "_find_duplicate",
                new_callable=AsyncMock,
                return_value=existing_issue,
            ) as mock_find,
            patch.object(
                creator, "_append_comment", new_callable=AsyncMock,
            ) as mock_comment,
        ):
            url = await creator.create_or_update(
                FileNotFoundError("claude not found"),
                _ctx(),
                ErrorCategory.PERMANENT,
            )

        assert url == existing_issue["html_url"]
        mock_find.assert_awaited_once()
        mock_comment.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_empty_string_on_failure(self) -> None:
        """If anything blows up, return '' instead of propagating."""
        creator = _creator()

        with patch.object(
            creator,
            "_find_duplicate",
            new_callable=AsyncMock,
            side_effect=RuntimeError("GitHub is down"),
        ):
            url = await creator.create_or_update(
                FileNotFoundError("x"),
                _ctx(),
                ErrorCategory.PERMANENT,
            )

        assert url == ""


# ===================================================================
# TestTokenResolution
# ===================================================================

class TestTokenResolution:
    """Token lookup priority: explicit > GITHUB_TOKEN > GH_TOKEN."""

    def test_explicit_token(self) -> None:
        creator = IssueCreator(github_token="explicit-tok")
        assert creator._get_token() == "explicit-tok"

    def test_github_token_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "env-tok")
        monkeypatch.delenv("GH_TOKEN", raising=False)
        creator = IssueCreator()
        assert creator._get_token() == "env-tok"

    def test_gh_token_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "gh-tok")
        creator = IssueCreator()
        assert creator._get_token() == "gh-tok"

    def test_no_token_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        creator = IssueCreator()
        with pytest.raises(ValueError, match="No GitHub token"):
            creator._get_token()
