"""Tests for the agent-user interaction module."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from apps.orchestrator.agent_interaction import (
    AgentInteraction,
    IssueTriage,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _agent() -> AgentInteraction:
    """Build an AgentInteraction with an explicit token (avoids env lookup)."""
    return AgentInteraction(github_token="ghp_test_token")


# ===================================================================
# TestIssueTriage — enum values
# ===================================================================


class TestIssueTriage:
    """IssueTriage enum has the expected members and string values."""

    def test_bug_value(self) -> None:
        assert IssueTriage.BUG == "bug"

    def test_question_value(self) -> None:
        assert IssueTriage.QUESTION == "question"

    def test_user_error_value(self) -> None:
        assert IssueTriage.USER_ERROR == "user_error"

    def test_unclear_value(self) -> None:
        assert IssueTriage.UNCLEAR == "unclear"

    def test_feature_value(self) -> None:
        assert IssueTriage.FEATURE == "feature"


# ===================================================================
# TestTriageClassification — rule-based classification
# ===================================================================


class TestTriageClassification:
    """classify_issue() applies patterns in priority order."""

    def test_traceback_classified_as_bug(self) -> None:
        """Body containing 'Traceback' -> BUG."""
        agent = _agent()
        result = agent.classify_issue(
            title="App crashes on startup",
            body="Traceback (most recent call last):\n  File ...",
        )
        assert result == IssueTriage.BUG

    def test_how_do_i_classified_as_question(self) -> None:
        """Title starting with 'How do I ...' -> QUESTION."""
        agent = _agent()
        result = agent.classify_issue(
            title="How do I configure the runner?",
            body="I need help with configuration.",
        )
        assert result == IssueTriage.QUESTION

    def test_401_with_api_key_classified_as_user_error(self) -> None:
        """Title with '401' and body with 'API_KEY' -> USER_ERROR."""
        agent = _agent()
        result = agent.classify_issue(
            title="401 when running agent",
            body="I set my API_KEY in .env but still get unauthorized.",
        )
        assert result == IssueTriage.USER_ERROR

    def test_add_support_classified_as_feature(self) -> None:
        """Title 'Add support for Mistral' -> FEATURE."""
        agent = _agent()
        result = agent.classify_issue(
            title="Add support for Mistral",
            body="It would be useful to support Mistral models.",
        )
        assert result == IssueTriage.FEATURE

    def test_vague_issue_classified_as_unclear(self) -> None:
        """Vague title and body with no matching patterns -> UNCLEAR."""
        agent = _agent()
        result = agent.classify_issue(
            title="it doesn't work",
            body="help",
        )
        assert result == IssueTriage.UNCLEAR


# ===================================================================
# TestClarificationComment — rendered Markdown
# ===================================================================


class TestClarificationComment:
    """_render_clarification() produces well-formed Markdown."""

    def test_rendered_body_contains_question(self) -> None:
        agent = _agent()
        body = agent._render_clarification(
            question="Which model should be used?",
            options=["claude-opus-4", "gpt-4o"],
        )
        assert "Which model should be used?" in body

    def test_rendered_body_contains_all_options(self) -> None:
        agent = _agent()
        options = ["Option A", "Option B", "Option C"]
        body = agent._render_clarification(
            question="Pick one",
            options=options,
        )
        for opt in options:
            assert opt in body

    def test_rendered_body_uses_checkbox_format(self) -> None:
        agent = _agent()
        body = agent._render_clarification(
            question="Pick one",
            options=["Alpha", "Beta"],
        )
        assert "- [ ] Alpha" in body
        assert "- [ ] Beta" in body
        assert "- [ ] Other: reply with your preference" in body


# ===================================================================
# TestPostComment — async actions (mocked HTTP)
# ===================================================================


class TestPostComment:
    """Public async methods delegate to _post_comment and _replace_label."""

    @pytest.mark.asyncio
    async def test_ask_clarification_calls_post_comment(self) -> None:
        """ask_clarification() calls _post_comment with rendered body."""
        agent = _agent()

        with (
            patch.object(
                agent, "_post_comment", new_callable=AsyncMock,
            ) as mock_post,
            patch(
                "apps.orchestrator.agent_interaction.httpx.AsyncClient",
            ) as mock_client_cls,
        ):
            mock_client = AsyncMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_resp = AsyncMock()
            mock_resp.raise_for_status = lambda: None
            mock_client.post = AsyncMock(return_value=mock_resp)
            mock_client_cls.return_value = mock_client

            await agent.ask_clarification(
                issue_number=42,
                question="Which engine?",
                options=["claude-code", "aider"],
            )

        mock_post.assert_awaited_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 42  # issue_number
        assert "Which engine?" in call_args[0][1]  # body contains question

    @pytest.mark.asyncio
    async def test_post_result_calls_post_comment(self) -> None:
        """post_result() calls _post_comment with result body."""
        agent = _agent()

        with patch.object(
            agent, "_post_comment", new_callable=AsyncMock,
        ) as mock_post:
            await agent.post_result(
                issue_number=99,
                result="Task completed successfully.",
                pr_url="https://github.com/korentomas/agentic-factory/pull/5",
            )

        mock_post.assert_awaited_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 99
        assert "Task completed successfully." in call_args[0][1]
        assert "pull/5" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_answer_question_calls_post_comment_and_replace_label(self) -> None:
        """answer_question() calls _post_comment AND _replace_label(bug -> question)."""
        agent = _agent()

        with (
            patch.object(
                agent, "_post_comment", new_callable=AsyncMock,
            ) as mock_post,
            patch.object(
                agent, "_replace_label", new_callable=AsyncMock,
            ) as mock_label,
        ):
            await agent.answer_question(
                issue_number=7,
                answer="You need to set the GITHUB_TOKEN env var.",
            )

        mock_post.assert_awaited_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == 7
        assert "GITHUB_TOKEN" in call_args[0][1]

        mock_label.assert_awaited_once_with(7, "bug", "question")
