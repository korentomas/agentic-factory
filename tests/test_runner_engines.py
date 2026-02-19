"""Tests for apps.runner.engines — protocol, adapters, and registry."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.runner.engines.aider import AiderAdapter, _parse_aider_cost
from apps.runner.engines.claude_code import (
    ClaudeCodeAdapter,
    _parse_claude_output,
)
from apps.runner.engines.protocol import AgentEngine
from apps.runner.engines.registry import (
    get_engine,
    reset_registry,
    select_engine,
)
from apps.runner.engines.subprocess_util import SubprocessResult, tail
from apps.runner.models import RunnerTask

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_task(**overrides):
    defaults = {
        "task_id": "test-1",
        "repo_url": "https://github.com/org/repo",
        "branch": "agent/test-1",
        "base_branch": "main",
        "description": "Fix the bug",
    }
    defaults.update(overrides)
    task = RunnerTask(**defaults)
    # Set workspace_path for engine tests
    object.__setattr__(task, "workspace_path", Path("/tmp/fake-workspace"))
    return task


# ── Protocol conformance ─────────────────────────────────────────────────────


class TestAgentEngineProtocol:
    """Verify adapters satisfy the AgentEngine protocol."""

    def test_claude_code_is_agent_engine(self):
        adapter = ClaudeCodeAdapter()
        assert isinstance(adapter, AgentEngine)

    def test_aider_is_agent_engine(self):
        adapter = AiderAdapter()
        assert isinstance(adapter, AgentEngine)


class TestClaudeCodeAdapter:
    """Tests for ClaudeCodeAdapter."""

    def test_name(self):
        assert ClaudeCodeAdapter().name == "claude-code"

    def test_supported_models(self):
        models = ClaudeCodeAdapter().supported_models
        assert "claude-sonnet-4-6" in models
        assert "claude-opus-4-6" in models

    @pytest.mark.asyncio
    async def test_run_success(self):
        task = _make_task()
        mock_result = SubprocessResult(
            return_code=0,
            stdout=json.dumps({"cost_usd": 0.12, "num_turns": 8}),
            stderr="",
            duration_ms=30000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = ClaudeCodeAdapter()
            result = await adapter.run(task)

        assert result.status == "success"
        assert result.cost_usd == 0.12
        assert result.num_turns == 8
        assert result.duration_ms == 30000
        assert result.engine == "claude-code"

    @pytest.mark.asyncio
    async def test_run_failure(self):
        task = _make_task()
        mock_result = SubprocessResult(
            return_code=1,
            stdout="",
            stderr="Error: API key invalid",
            duration_ms=5000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = ClaudeCodeAdapter()
            result = await adapter.run(task)

        assert result.status == "failure"
        assert "API key invalid" in result.error_message

    @pytest.mark.asyncio
    async def test_run_timeout(self):
        task = _make_task()
        mock_result = SubprocessResult(
            return_code=-1,
            stdout="",
            stderr="Process killed: timeout exceeded",
            duration_ms=3600000,
            timed_out=True,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = ClaudeCodeAdapter()
            result = await adapter.run(task)

        assert result.status == "timeout"

    @pytest.mark.asyncio
    async def test_run_no_workspace(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        adapter = ClaudeCodeAdapter()
        result = await adapter.run(task)
        assert result.status == "failure"
        assert "workspace" in result.error_message.lower()


class TestParseClaudeOutput:
    """Tests for Claude JSON output parsing."""

    def test_valid_json(self):
        stdout = json.dumps({"cost_usd": 0.25, "num_turns": 15})
        cost, turns = _parse_claude_output(stdout)
        assert cost == 0.25
        assert turns == 15

    def test_ndjson_last_line(self):
        lines = [
            json.dumps({"type": "progress"}),
            json.dumps({"type": "progress"}),
            json.dumps({"cost_usd": 0.50, "num_turns": 20}),
        ]
        stdout = "\n".join(lines)
        cost, turns = _parse_claude_output(stdout)
        assert cost == 0.50
        assert turns == 20

    def test_empty_stdout(self):
        cost, turns = _parse_claude_output("")
        assert cost == 0.0
        assert turns == 0

    def test_invalid_json(self):
        cost, turns = _parse_claude_output("not json at all")
        assert cost == 0.0
        assert turns == 0

    def test_null_cost(self):
        stdout = json.dumps({"cost_usd": None, "num_turns": 5})
        cost, turns = _parse_claude_output(stdout)
        assert cost == 0.0
        assert turns == 5


class TestAiderAdapter:
    """Tests for AiderAdapter."""

    def test_name(self):
        assert AiderAdapter().name == "aider"

    def test_supported_models_wildcard(self):
        assert AiderAdapter().supported_models == ["*"]

    @pytest.mark.asyncio
    async def test_run_success(self):
        task = _make_task(model="deepseek/deepseek-chat")
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Tokens: 12.3k sent. Cost: $0.03",
            stderr="",
            duration_ms=20000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = AiderAdapter()
            result = await adapter.run(task)

        assert result.status == "success"
        assert result.cost_usd == 0.03
        assert result.engine == "aider"


class TestParseAiderCost:
    """Tests for aider cost extraction."""

    def test_with_cost(self):
        assert _parse_aider_cost("Tokens: 12.3k sent. Cost: $0.05") == 0.05

    def test_without_cost(self):
        assert _parse_aider_cost("Done!") == 0.0

    def test_integer_cost(self):
        assert _parse_aider_cost("Cost: $2") == 2.0


class TestEngineRegistry:
    """Tests for engine registry and selection."""

    def setup_method(self):
        reset_registry()

    def teardown_method(self):
        reset_registry()

    def test_get_claude_code(self):
        engine = get_engine("claude-code")
        assert engine.name == "claude-code"

    def test_get_aider(self):
        engine = get_engine("aider")
        assert engine.name == "aider"

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown engine"):
            get_engine("nonexistent")

    def test_select_claude_model(self):
        engine = select_engine(model="claude-sonnet-4-6")
        assert engine.name == "claude-code"

    def test_select_non_claude_falls_back_to_aider(self):
        engine = select_engine(model="deepseek-chat")
        assert engine.name == "aider"

    def test_select_preferred_override(self):
        engine = select_engine(model="claude-sonnet-4-6", preferred_engine="aider")
        assert engine.name == "aider"

    def test_select_env_override(self, monkeypatch):
        monkeypatch.setenv("LAILATOV_ENGINE", "aider")
        engine = select_engine(model="claude-sonnet-4-6")
        assert engine.name == "aider"

    def test_select_no_model_falls_back(self):
        engine = select_engine()
        assert engine.name == "aider"


class TestTail:
    """Tests for output tail utility."""

    def test_short_text(self):
        assert tail("hello", limit=100) == "hello"

    def test_long_text_truncated(self):
        text = "x" * 10000
        result = tail(text, limit=100)
        assert len(result) < 10000
        assert result.startswith("...truncated...")
        assert result.endswith("x" * 100)
