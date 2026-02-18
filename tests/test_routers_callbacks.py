"""
Tests for the callbacks router — GitHub Actions callback handlers.

Covers:
- Endpoint behavior for /callbacks/agent-complete, /callbacks/review-clean, /callbacks/blocked
- X-Callback-Secret verification (valid, invalid, missing, unconfigured)
- Outbound notification helpers (_post_slack, _post_clickup_comment)
- Branch name parsing (_extract_task_id_from_branch)
- Pydantic model validation for all payload types
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from apps.orchestrator.routers.callbacks import (
    AgentCompletePayload,
    BlockedPayload,
    ReviewCleanPayload,
    _extract_task_id_from_branch,
    _post_clickup_comment,
    _post_slack,
)

# ── Secret verification ──────────────────────────────────────────────────────


class TestCallbackSecretVerification:
    """Verify X-Callback-Secret header enforcement across all endpoints."""

    def test_missing_secret_header_returns_401(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        """A request without X-Callback-Secret should be rejected with 401."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={"clickup_task_id": "abc123", "status": "success"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid callback secret"

    def test_wrong_secret_header_returns_401(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        """A request with the wrong secret should be rejected with 401."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={"clickup_task_id": "abc123", "status": "success"},
            headers={"X-Callback-Secret": "wrong-secret"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid callback secret"

    def test_valid_secret_header_returns_200(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """A request with the correct secret should be accepted."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={"clickup_task_id": "abc123", "status": "success"},
            headers={"X-Callback-Secret": env_vars["CALLBACK_SECRET"]},
        )
        assert resp.status_code == 200

    def test_no_callback_secret_configured_non_production_allows_request(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        mock_httpx_post: AsyncMock,
    ) -> None:
        """When CALLBACK_SECRET is unset in non-production, requests pass through."""
        monkeypatch.delenv("CALLBACK_SECRET")
        monkeypatch.setenv("ENVIRONMENT", "development")
        resp = client.post(
            "/callbacks/agent-complete",
            json={"clickup_task_id": "abc123", "status": "success"},
        )
        assert resp.status_code == 200

    def test_no_callback_secret_configured_production_still_allows_request(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        monkeypatch: pytest.MonkeyPatch,
        mock_httpx_post: AsyncMock,
    ) -> None:
        """When CALLBACK_SECRET is unset in production, requests still pass (with a warning)."""
        monkeypatch.delenv("CALLBACK_SECRET")
        monkeypatch.setenv("ENVIRONMENT", "production")
        resp = client.post(
            "/callbacks/agent-complete",
            json={"clickup_task_id": "abc123", "status": "success"},
        )
        # The code logs a warning but still allows the request through
        assert resp.status_code == 200

    def test_secret_verified_on_review_clean_endpoint(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        """review-clean also enforces secret verification."""
        resp = client.post(
            "/callbacks/review-clean",
            json={"pr_url": "https://github.com/org/repo/pull/1", "pr_number": 1},
            headers={"X-Callback-Secret": "wrong-secret"},
        )
        assert resp.status_code == 401

    def test_secret_verified_on_blocked_endpoint(
        self, client: TestClient, env_vars: dict[str, str]
    ) -> None:
        """blocked also enforces secret verification."""
        resp = client.post(
            "/callbacks/blocked",
            json={"pr_url": "https://github.com/org/repo/pull/1", "pr_number": 1},
            headers={"X-Callback-Secret": "wrong-secret"},
        )
        assert resp.status_code == 401


# ── POST /callbacks/agent-complete ────────────────────────────────────────────


class TestAgentComplete:
    """Tests for the agent-complete callback endpoint."""

    def _headers(self, env_vars: dict[str, str]) -> dict[str, str]:
        return {"X-Callback-Secret": env_vars["CALLBACK_SECRET"]}

    def test_success_status_returns_ok(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Success status is acknowledged without triggering failure notifications."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={
                "clickup_task_id": "abc123",
                "status": "success",
                "pr_url": "https://github.com/org/repo/pull/42",
                "branch": "agent/cu-abc123",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["received"] == "success"
        # On success, no outbound HTTP calls should be made
        mock_httpx_post.post.assert_not_called()

    def test_failure_status_triggers_slack_and_clickup(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Failure status should post to both Slack and ClickUp."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={
                "clickup_task_id": "task99",
                "status": "failure",
                "run_id": "12345",
                "branch": "agent/cu-task99",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["received"] == "failure"

        # Should have called post twice: once for Slack, once for ClickUp
        assert mock_httpx_post.post.call_count == 2

        # First call = Slack
        slack_call = mock_httpx_post.post.call_args_list[0]
        assert slack_call[0][0] == env_vars["SLACK_WEBHOOK_URL"]
        slack_payload = slack_call[1]["json"]
        assert "failure" in slack_payload["text"]
        assert "task99" in slack_payload["text"]

        # Second call = ClickUp
        clickup_call = mock_httpx_post.post.call_args_list[1]
        assert "clickup.com" in clickup_call[0][0]
        assert "task99" in clickup_call[0][0]

    def test_cancelled_status_triggers_notifications(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Cancelled status is treated like failure and triggers notifications."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={
                "clickup_task_id": "task_c",
                "status": "cancelled",
                "run_id": "run_c",
                "branch": "agent/cu-task_c",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        assert resp.json()["received"] == "cancelled"
        # Slack + ClickUp
        assert mock_httpx_post.post.call_count == 2

    def test_failure_with_no_clickup_task_id_skips_clickup(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Failure with empty task ID still sends Slack, but skips ClickUp comment."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={
                "clickup_task_id": "",
                "status": "failure",
                "run_id": "run_x",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        # Only Slack (ClickUp skipped because task_id is empty/falsy)
        assert mock_httpx_post.post.call_count == 1
        slack_call = mock_httpx_post.post.call_args_list[0]
        assert slack_call[0][0] == env_vars["SLACK_WEBHOOK_URL"]

    def test_failure_includes_actions_url_when_run_id_and_repo_present(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """The Slack and ClickUp messages should include a link to the GitHub Actions run."""
        resp = client.post(
            "/callbacks/agent-complete",
            json={
                "clickup_task_id": "tid",
                "status": "failure",
                "run_id": "98765",
                "branch": "agent/cu-tid",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200

        slack_call = mock_httpx_post.post.call_args_list[0]
        slack_text = slack_call[1]["json"]["text"]
        assert "98765" in slack_text
        assert env_vars["GITHUB_REPO"] in slack_text


# ── POST /callbacks/review-clean ──────────────────────────────────────────────


class TestReviewClean:
    """Tests for the review-clean callback endpoint."""

    def _headers(self, env_vars: dict[str, str]) -> dict[str, str]:
        return {"X-Callback-Secret": env_vars["CALLBACK_SECRET"]}

    def test_review_clean_triggers_notifications(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """A clean review should post to both Slack and ClickUp."""
        resp = client.post(
            "/callbacks/review-clean",
            json={
                "pr_url": "https://github.com/org/repo/pull/10",
                "pr_number": 10,
                "branch": "agent/cu-task456",
                "risk_tier": "low",
                "run_id": "run_rc",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # ClickUp comment + Slack post
        assert mock_httpx_post.post.call_count == 2

        # Find the ClickUp call (URL contains clickup.com)
        clickup_calls = [
            c for c in mock_httpx_post.post.call_args_list
            if "clickup.com" in str(c)
        ]
        assert len(clickup_calls) == 1
        assert "task456" in clickup_calls[0][0][0]

        # Find the Slack call
        slack_calls = [
            c for c in mock_httpx_post.post.call_args_list
            if "slack" in str(c)
        ]
        assert len(slack_calls) == 1
        slack_text = slack_calls[0][1]["json"]["text"]
        assert "#10" in slack_text
        assert "low" in slack_text

    def test_review_clean_without_branch_skips_clickup(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """When branch is empty/non-matching, task_id extraction fails; ClickUp is skipped."""
        resp = client.post(
            "/callbacks/review-clean",
            json={
                "pr_url": "https://github.com/org/repo/pull/11",
                "pr_number": 11,
                "branch": "main",
                "risk_tier": "medium",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        # Only Slack (no task ID extracted from "main")
        assert mock_httpx_post.post.call_count == 1
        slack_call = mock_httpx_post.post.call_args_list[0]
        assert slack_call[0][0] == env_vars["SLACK_WEBHOOK_URL"]

    def test_review_clean_includes_risk_tier_in_slack_message(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Slack message should include the risk tier for reviewer context."""
        resp = client.post(
            "/callbacks/review-clean",
            json={
                "pr_url": "https://github.com/org/repo/pull/20",
                "pr_number": 20,
                "branch": "agent/cu-xyz",
                "risk_tier": "high",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        slack_calls = [
            c for c in mock_httpx_post.post.call_args_list
            if "slack" in str(c)
        ]
        slack_text = slack_calls[0][1]["json"]["text"]
        assert "high" in slack_text


# ── POST /callbacks/blocked ───────────────────────────────────────────────────


class TestBlocked:
    """Tests for the blocked callback endpoint."""

    def _headers(self, env_vars: dict[str, str]) -> dict[str, str]:
        return {"X-Callback-Secret": env_vars["CALLBACK_SECRET"]}

    def test_blocked_triggers_notifications(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """A blocked callback should post to both Slack and ClickUp."""
        resp = client.post(
            "/callbacks/blocked",
            json={
                "pr_url": "https://github.com/org/repo/pull/15",
                "pr_number": 15,
                "branch": "agent/cu-blk001",
                "reason": "test-failures",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        assert resp.json()["ok"] is True

        # Slack + ClickUp
        assert mock_httpx_post.post.call_count == 2

    def test_blocked_non_escalation_uses_warning_messaging(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Non-escalation blocked callback uses warning-level messaging."""
        resp = client.post(
            "/callbacks/blocked",
            json={
                "pr_url": "https://github.com/org/repo/pull/16",
                "pr_number": 16,
                "branch": "agent/cu-blk002",
                "reason": "lint-errors",
                "escalation": False,
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        slack_calls = [
            c for c in mock_httpx_post.post.call_args_list
            if "slack" in str(c)
        ]
        slack_text = slack_calls[0][1]["json"]["text"]
        assert "blocked" in slack_text.lower()
        assert "lint-errors" in slack_text

    def test_blocked_with_escalation_flag_uses_escalation_messaging(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Escalation=true triggers remediation-limit-reached messaging."""
        resp = client.post(
            "/callbacks/blocked",
            json={
                "pr_url": "https://github.com/org/repo/pull/17",
                "pr_number": 17,
                "branch": "agent/cu-blk003",
                "reason": "blocking-findings",
                "escalation": True,
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        slack_calls = [
            c for c in mock_httpx_post.post.call_args_list
            if "slack" in str(c)
        ]
        slack_text = slack_calls[0][1]["json"]["text"]
        assert "remediation limit" in slack_text.lower()
        assert "human review" in slack_text.lower()

    def test_blocked_with_max_remediation_reason_triggers_escalation(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """reason='max-remediation-rounds' triggers escalation even without escalation=true."""
        resp = client.post(
            "/callbacks/blocked",
            json={
                "pr_url": "https://github.com/org/repo/pull/18",
                "pr_number": 18,
                "branch": "agent/cu-blk004",
                "reason": "max-remediation-rounds",
                "escalation": False,
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        slack_calls = [
            c for c in mock_httpx_post.post.call_args_list
            if "slack" in str(c)
        ]
        slack_text = slack_calls[0][1]["json"]["text"]
        assert "remediation limit" in slack_text.lower()

    def test_blocked_escalation_clickup_mentions_manual_fix(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """Escalation ClickUp comment should tell the human to fix manually."""
        resp = client.post(
            "/callbacks/blocked",
            json={
                "pr_url": "https://github.com/org/repo/pull/19",
                "pr_number": 19,
                "branch": "agent/cu-blk005",
                "reason": "max-remediation-rounds",
                "escalation": True,
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        clickup_calls = [
            c for c in mock_httpx_post.post.call_args_list
            if "clickup.com" in str(c)
        ]
        assert len(clickup_calls) == 1
        clickup_body = clickup_calls[0][1]["json"]["comment_text"]
        assert "fix manually" in clickup_body.lower()
        assert "2 rounds" in clickup_body

    def test_blocked_without_task_id_skips_clickup(
        self,
        client: TestClient,
        env_vars: dict[str, str],
        mock_httpx_post: AsyncMock,
    ) -> None:
        """When branch doesn't contain a task ID, ClickUp comment is skipped."""
        resp = client.post(
            "/callbacks/blocked",
            json={
                "pr_url": "https://github.com/org/repo/pull/21",
                "pr_number": 21,
                "branch": "feature/something",
                "reason": "lint-errors",
            },
            headers=self._headers(env_vars),
        )
        assert resp.status_code == 200
        # Only Slack
        assert mock_httpx_post.post.call_count == 1
        assert "slack" in str(mock_httpx_post.post.call_args_list[0]).lower()


# ── _post_slack ───────────────────────────────────────────────────────────────


class TestPostSlack:
    """Tests for the _post_slack notification helper."""

    @pytest.mark.asyncio
    async def test_post_slack_succeeds(
        self, env_vars: dict[str, str], mock_httpx_post: AsyncMock
    ) -> None:
        """A successful Slack post should not raise any exception."""
        await _post_slack("test message")
        mock_httpx_post.post.assert_called_once()
        call_args = mock_httpx_post.post.call_args
        assert call_args[0][0] == env_vars["SLACK_WEBHOOK_URL"]
        payload = call_args[1]["json"]
        assert payload["text"] == "test message"
        assert payload["channel"] == env_vars["SLACK_CHANNEL"]

    @pytest.mark.asyncio
    async def test_post_slack_skipped_when_url_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When SLACK_WEBHOOK_URL is not set, _post_slack returns silently."""
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
        # Should not raise
        await _post_slack("test message")

    @pytest.mark.asyncio
    async def test_post_slack_http_error_does_not_raise(
        self, env_vars: dict[str, str]
    ) -> None:
        """HTTP errors from Slack are logged and swallowed, never raised."""
        mock_response = AsyncMock()
        mock_response.status_code = 500
        mock_response.text = "server error"
        mock_response.raise_for_status = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Server Error",
                request=httpx.Request("POST", "https://hooks.slack.com/test"),
                response=httpx.Response(500, text="server error"),
            )
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Must not raise
            await _post_slack("test message")

    @pytest.mark.asyncio
    async def test_post_slack_request_error_does_not_raise(
        self, env_vars: dict[str, str]
    ) -> None:
        """Network/connection errors from Slack are logged and swallowed."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.RequestError(
                "Connection refused",
                request=httpx.Request("POST", "https://hooks.slack.com/test"),
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Must not raise
            await _post_slack("test message")


# ── _post_clickup_comment ─────────────────────────────────────────────────────


class TestPostClickUpComment:
    """Tests for the _post_clickup_comment notification helper."""

    @pytest.mark.asyncio
    async def test_post_clickup_comment_succeeds(
        self, env_vars: dict[str, str], mock_httpx_post: AsyncMock
    ) -> None:
        """A successful ClickUp comment should not raise any exception."""
        await _post_clickup_comment("task123", "Hello from agent")
        mock_httpx_post.post.assert_called_once()
        call_args = mock_httpx_post.post.call_args
        assert "task123" in call_args[0][0]
        assert call_args[1]["json"]["comment_text"] == "Hello from agent"
        assert call_args[1]["headers"]["Authorization"] == env_vars["CLICKUP_API_TOKEN"]

    @pytest.mark.asyncio
    async def test_post_clickup_comment_skipped_when_token_not_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When CLICKUP_API_TOKEN is not set, _post_clickup_comment returns silently."""
        monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
        # Should not raise
        await _post_clickup_comment("task123", "Hello")

    @pytest.mark.asyncio
    async def test_post_clickup_comment_http_error_does_not_raise(
        self, env_vars: dict[str, str]
    ) -> None:
        """HTTP errors from ClickUp are logged and swallowed, never raised."""
        mock_response = AsyncMock()
        mock_response.status_code = 403
        mock_response.text = "forbidden"
        mock_response.raise_for_status = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Forbidden",
                request=httpx.Request(
                    "POST", "https://api.clickup.com/api/v2/task/t/comment"
                ),
                response=httpx.Response(403, text="forbidden"),
            )
        )
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Must not raise
            await _post_clickup_comment("task123", "Hello")

    @pytest.mark.asyncio
    async def test_post_clickup_comment_request_error_does_not_raise(
        self, env_vars: dict[str, str]
    ) -> None:
        """Network/connection errors to ClickUp are logged and swallowed."""
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(
            side_effect=httpx.RequestError(
                "DNS resolution failed",
                request=httpx.Request(
                    "POST", "https://api.clickup.com/api/v2/task/t/comment"
                ),
            )
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            # Must not raise
            await _post_clickup_comment("task123", "Hello")


# ── _extract_task_id_from_branch ──────────────────────────────────────────────


class TestExtractTaskIdFromBranch:
    """Tests for branch-name-to-ClickUp-task-ID extraction."""

    def test_standard_agent_branch(self) -> None:
        """agent/cu-{id} is the expected format."""
        assert _extract_task_id_from_branch("agent/cu-abc123def") == "abc123def"

    def test_short_task_id(self) -> None:
        """Short alphanumeric IDs should still be extracted."""
        assert _extract_task_id_from_branch("agent/cu-86bx3m") == "86bx3m"

    def test_main_branch_returns_empty(self) -> None:
        """Non-agent branches should return empty string."""
        assert _extract_task_id_from_branch("main") == ""

    def test_empty_string_returns_empty(self) -> None:
        """Empty branch name should return empty string."""
        assert _extract_task_id_from_branch("") == ""

    def test_feature_branch_returns_empty(self) -> None:
        """Feature branches without cu- prefix return empty string."""
        assert _extract_task_id_from_branch("feature/add-login") == ""

    def test_branch_with_nested_slashes(self) -> None:
        """Only the last segment after / is checked for cu- prefix."""
        assert _extract_task_id_from_branch("refs/heads/agent/cu-task789") == "task789"

    def test_branch_with_cu_prefix_no_slash(self) -> None:
        """A branch like 'cu-xyz' (no slash) should still extract the ID."""
        assert _extract_task_id_from_branch("cu-xyz") == "xyz"

    def test_branch_with_cu_but_not_prefix(self) -> None:
        """A segment containing 'cu-' but not starting with it returns empty."""
        assert _extract_task_id_from_branch("agent/mycu-task") == ""

    def test_branch_cu_with_empty_id(self) -> None:
        """'cu-' with nothing after it returns empty string (the ID portion is empty)."""
        assert _extract_task_id_from_branch("agent/cu-") == ""


# ── Pydantic model validation ─────────────────────────────────────────────────


class TestAgentCompletePayloadValidation:
    """Validation tests for AgentCompletePayload."""

    def test_minimal_valid_payload(self) -> None:
        """Only clickup_task_id is required."""
        p = AgentCompletePayload(clickup_task_id="abc123")
        assert p.clickup_task_id == "abc123"
        assert p.status == "unknown"
        assert p.correlation_id == ""
        assert p.run_id == ""
        assert p.branch == ""
        assert p.pr_url == ""

    def test_all_fields_populated(self) -> None:
        """All fields can be provided."""
        p = AgentCompletePayload(
            clickup_task_id="t1",
            correlation_id="corr-1",
            run_id="run-1",
            branch="agent/cu-t1",
            pr_url="https://github.com/org/repo/pull/5",
            status="success",
        )
        assert p.clickup_task_id == "t1"
        assert p.status == "success"

    def test_valid_status_values(self) -> None:
        """All four valid status values should be accepted."""
        for s in ("success", "failure", "cancelled", "unknown"):
            p = AgentCompletePayload(clickup_task_id="t", status=s)
            assert p.status == s

    def test_invalid_status_rejected(self) -> None:
        """An invalid status value should raise a validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AgentCompletePayload(clickup_task_id="t", status="pending")
        errors = exc_info.value.errors()
        assert any("status" in str(e.get("loc", "")) for e in errors)

    def test_missing_clickup_task_id_rejected(self) -> None:
        """clickup_task_id is required and cannot be omitted."""
        with pytest.raises(ValidationError):
            AgentCompletePayload()  # type: ignore[call-arg]


class TestReviewCleanPayloadValidation:
    """Validation tests for ReviewCleanPayload."""

    def test_minimal_valid_payload(self) -> None:
        """pr_url and pr_number are required."""
        p = ReviewCleanPayload(
            pr_url="https://github.com/org/repo/pull/1", pr_number=1
        )
        assert p.pr_url == "https://github.com/org/repo/pull/1"
        assert p.pr_number == 1
        assert p.branch == ""
        assert p.risk_tier == ""
        assert p.run_id == ""

    def test_all_fields_populated(self) -> None:
        p = ReviewCleanPayload(
            pr_url="https://github.com/org/repo/pull/5",
            pr_number=5,
            branch="agent/cu-id",
            risk_tier="high",
            run_id="run123",
        )
        assert p.risk_tier == "high"
        assert p.branch == "agent/cu-id"

    def test_missing_pr_url_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewCleanPayload(pr_number=1)  # type: ignore[call-arg]

    def test_missing_pr_number_rejected(self) -> None:
        with pytest.raises(ValidationError):
            ReviewCleanPayload(pr_url="https://github.com/org/repo/pull/1")  # type: ignore[call-arg]


class TestBlockedPayloadValidation:
    """Validation tests for BlockedPayload."""

    def test_minimal_valid_payload(self) -> None:
        """pr_url and pr_number are required."""
        p = BlockedPayload(
            pr_url="https://github.com/org/repo/pull/2", pr_number=2
        )
        assert p.pr_url == "https://github.com/org/repo/pull/2"
        assert p.pr_number == 2
        assert p.branch == ""
        assert p.reason == ""
        assert p.run_id == ""
        assert p.escalation is False

    def test_escalation_defaults_to_false(self) -> None:
        p = BlockedPayload(
            pr_url="https://github.com/org/repo/pull/3", pr_number=3
        )
        assert p.escalation is False

    def test_escalation_can_be_true(self) -> None:
        p = BlockedPayload(
            pr_url="https://github.com/org/repo/pull/4",
            pr_number=4,
            escalation=True,
        )
        assert p.escalation is True

    def test_missing_pr_url_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BlockedPayload(pr_number=1)  # type: ignore[call-arg]

    def test_missing_pr_number_rejected(self) -> None:
        with pytest.raises(ValidationError):
            BlockedPayload(pr_url="https://github.com/org/repo/pull/1")  # type: ignore[call-arg]
