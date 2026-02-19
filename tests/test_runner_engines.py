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


class TestClaudeCodeAdapterEdgeCases:
    """Additional tests for ClaudeCodeAdapter env var injection and check_available."""

    @pytest.mark.asyncio
    async def test_run_injects_anthropic_api_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        task = _make_task()
        mock_result = SubprocessResult(
            return_code=0,
            stdout=json.dumps({"cost_usd": 0.05, "num_turns": 3}),
            stderr="",
            duration_ms=10000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_API_KEY"] == "sk-ant-test"

    @pytest.mark.asyncio
    async def test_run_injects_base_url(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
        task = _make_task()
        mock_result = SubprocessResult(
            return_code=0,
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
            stderr="",
            duration_ms=5000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"

    @pytest.mark.asyncio
    async def test_run_passes_stdin_text(self):
        task = _make_task(description="Fix the login form")
        mock_result = SubprocessResult(
            return_code=0,
            stdout=json.dumps({"cost_usd": 0.1, "num_turns": 5}),
            stderr="",
            duration_ms=15000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        assert mock_run.call_args.kwargs["stdin_text"] == "Fix the login form"

    @pytest.mark.asyncio
    async def test_check_available_success(self):
        mock_result = SubprocessResult(
            return_code=0,
            stdout="claude-code v1.0.0",
            stderr="",
            duration_ms=300,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = ClaudeCodeAdapter()
            assert await adapter.check_available() is True

    @pytest.mark.asyncio
    async def test_check_available_not_found(self):
        mock_result = SubprocessResult(
            return_code=127,
            stdout="",
            stderr="command not found: claude",
            duration_ms=100,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = ClaudeCodeAdapter()
            assert await adapter.check_available() is False

    @pytest.mark.asyncio
    async def test_run_default_model(self):
        """When no model is set, defaults to claude-sonnet-4-6."""
        task = _make_task(model="")
        mock_result = SubprocessResult(
            return_code=0,
            stdout=json.dumps({"cost_usd": 0.1, "num_turns": 5}),
            stderr="",
            duration_ms=10000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            result = await adapter.run(task)

        assert result.model == "claude-sonnet-4-6"
        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "claude-sonnet-4-6"


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


class TestAiderAdapterEdgeCases:
    """Additional edge-case tests for AiderAdapter."""

    @pytest.mark.asyncio
    async def test_run_failure(self):
        task = _make_task(model="gpt-4.1")
        mock_result = SubprocessResult(
            return_code=1,
            stdout="",
            stderr="Error: Model not available",
            duration_ms=5000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = AiderAdapter()
            result = await adapter.run(task)

        assert result.status == "failure"
        assert "Model not available" in result.error_message

    @pytest.mark.asyncio
    async def test_run_timeout(self):
        task = _make_task(model="deepseek-chat")
        mock_result = SubprocessResult(
            return_code=-1,
            stdout="",
            stderr="Process killed: timeout exceeded",
            duration_ms=3600000,
            timed_out=True,
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = AiderAdapter()
            result = await adapter.run(task)

        assert result.status == "timeout"
        assert result.duration_ms == 3600000

    @pytest.mark.asyncio
    async def test_run_no_workspace(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        adapter = AiderAdapter()
        result = await adapter.run(task)
        assert result.status == "failure"
        assert "workspace" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_run_default_model(self):
        """When no model is set, aider defaults to claude-sonnet-4-6."""
        task = _make_task(model="")
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done!",
            stderr="",
            duration_ms=10000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            adapter = AiderAdapter()
            result = await adapter.run(task)

        assert result.status == "success"
        # Check the command included the default model
        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_run_injects_api_key_for_openai_model(self, monkeypatch):
        """GPT models should have OPENAI_API_KEY injected."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        task = _make_task(model="gpt-4.1-mini")
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done!",
            stderr="",
            duration_ms=10000,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENAI_API_KEY"] == "sk-test-key"

    @pytest.mark.asyncio
    async def test_check_available_success(self):
        mock_result = SubprocessResult(
            return_code=0,
            stdout="aider v0.50.0",
            stderr="",
            duration_ms=500,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = AiderAdapter()
            assert await adapter.check_available() is True

    @pytest.mark.asyncio
    async def test_check_available_not_found(self):
        mock_result = SubprocessResult(
            return_code=127,
            stdout="",
            stderr="command not found: aider",
            duration_ms=100,
            timed_out=False,
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = AiderAdapter()
            assert await adapter.check_available() is False


class TestParseAiderCost:
    """Tests for aider cost extraction."""

    def test_with_cost(self):
        assert _parse_aider_cost("Tokens: 12.3k sent. Cost: $0.05") == 0.05

    def test_without_cost(self):
        assert _parse_aider_cost("Done!") == 0.0

    def test_integer_cost(self):
        assert _parse_aider_cost("Cost: $2") == 2.0

    def test_empty_string(self):
        assert _parse_aider_cost("") == 0.0

    def test_multiline_with_cost_on_last_line(self):
        stdout = "Editing file.py\nApplied changes\nTokens: 5k sent. Cost: $0.12"
        assert _parse_aider_cost(stdout) == 0.12


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
