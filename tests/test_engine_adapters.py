"""Comprehensive tests for engine adapters — ClaudeCode, Aider, and Gemini CLI.

Tests mock ``run_engine_subprocess`` (not ``asyncio.create_subprocess_exec``)
to exercise the full adapter logic deterministically: argument building,
env var injection, output parsing, and status mapping.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.runner.engines.aider import AiderAdapter
from apps.runner.engines.claude_code import ClaudeCodeAdapter
from apps.runner.engines.codex import CodexAdapter
from apps.runner.engines.gemini_cli import GeminiCliAdapter
from apps.runner.engines.pi import PiAdapter
from apps.runner.engines.subprocess_util import SubprocessResult
from apps.runner.models import RunnerTask

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_task(**overrides: object) -> RunnerTask:
    """Build a RunnerTask with workspace_path pre-set for engine tests."""
    defaults: dict[str, object] = {
        "task_id": "test-1",
        "repo_url": "https://github.com/org/repo",
        "branch": "agent/test-1",
        "base_branch": "main",
        "description": "Fix the bug in auth module",
    }
    defaults.update(overrides)
    task = RunnerTask(**defaults)  # type: ignore[arg-type]
    object.__setattr__(task, "workspace_path", Path("/tmp/fake-workspace"))
    return task


def _make_task_no_workspace(**overrides: object) -> RunnerTask:
    """Build a RunnerTask *without* workspace_path (simulates pre-clone state)."""
    defaults: dict[str, object] = {
        "task_id": "test-no-ws",
        "repo_url": "https://github.com/org/repo",
        "branch": "agent/test",
        "base_branch": "main",
        "description": "Task without workspace",
    }
    defaults.update(overrides)
    return RunnerTask(**defaults)  # type: ignore[arg-type]


def _subprocess_ok(
    stdout: str = "",
    stderr: str = "",
    duration_ms: int = 10000,
) -> SubprocessResult:
    """Build a successful SubprocessResult."""
    return SubprocessResult(
        return_code=0,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=False,
        cancelled=False,
    )


def _subprocess_fail(
    return_code: int = 1,
    stderr: str = "Something went wrong",
    duration_ms: int = 5000,
) -> SubprocessResult:
    """Build a failed SubprocessResult."""
    return SubprocessResult(
        return_code=return_code,
        stdout="",
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=False,
        cancelled=False,
    )


def _subprocess_timeout(duration_ms: int = 3600000) -> SubprocessResult:
    """Build a timed-out SubprocessResult."""
    return SubprocessResult(
        return_code=-9,
        stdout="",
        stderr="Process killed: timeout exceeded",
        duration_ms=duration_ms,
        timed_out=True,
        cancelled=False,
    )


def _subprocess_cancelled(duration_ms: int = 15000) -> SubprocessResult:
    """Build a cancelled SubprocessResult."""
    return SubprocessResult(
        return_code=-15,
        stdout="",
        stderr="Process cancelled",
        duration_ms=duration_ms,
        timed_out=False,
        cancelled=True,
    )


# ── ClaudeCodeAdapter tests ─────────────────────────────────────────────────

_CLAUDE_SUBPROCESS = "apps.runner.engines.claude_code.run_engine_subprocess"


class TestClaudeSuccessParsing:
    """ClaudeCodeAdapter: successful runs parse cost and turns from JSON output."""

    @pytest.mark.asyncio
    async def test_claude_success_parses_cost_and_turns(self) -> None:
        """Mock subprocess returns JSON output; verify cost_usd and num_turns parsed."""
        ndjson_output = "\n".join([
            json.dumps({"type": "progress", "message": "thinking..."}),
            json.dumps({"type": "progress", "message": "editing file"}),
            json.dumps({"cost_usd": 0.42, "num_turns": 12}),
        ])
        mock_result = _subprocess_ok(stdout=ndjson_output, duration_ms=45000)

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            adapter = ClaudeCodeAdapter()
            result = await adapter.run(_make_task())

        assert result.status == "success"
        assert result.cost_usd == 0.42
        assert result.num_turns == 12
        assert result.duration_ms == 45000
        assert result.engine == "claude-code"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_claude_success_single_json_line(self) -> None:
        """A single JSON line with cost and turns is parsed correctly."""
        stdout = json.dumps({"cost_usd": 1.23, "num_turns": 30})
        mock_result = _subprocess_ok(stdout=stdout)

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await ClaudeCodeAdapter().run(_make_task())

        assert result.cost_usd == 1.23
        assert result.num_turns == 30

    @pytest.mark.asyncio
    async def test_claude_success_missing_cost_defaults_zero(self) -> None:
        """If JSON lacks cost_usd, defaults to 0.0."""
        stdout = json.dumps({"num_turns": 5})
        mock_result = _subprocess_ok(stdout=stdout)

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await ClaudeCodeAdapter().run(_make_task())

        assert result.cost_usd == 0.0
        assert result.num_turns == 5

    @pytest.mark.asyncio
    async def test_claude_success_null_cost_defaults_zero(self) -> None:
        """OpenRouter returns cost: null — adapter handles gracefully."""
        stdout = json.dumps({"cost_usd": None, "num_turns": 7})
        mock_result = _subprocess_ok(stdout=stdout)

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await ClaudeCodeAdapter().run(_make_task())

        assert result.cost_usd == 0.0
        assert result.num_turns == 7


class TestClaudeTimeoutAndCancel:
    """ClaudeCodeAdapter: timeout and cancellation scenarios."""

    @pytest.mark.asyncio
    async def test_claude_timeout_returns_timeout_status(self) -> None:
        """Mock subprocess with timed_out=True produces status='timeout'."""
        mock_result = _subprocess_timeout(duration_ms=3600000)

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await ClaudeCodeAdapter().run(_make_task())

        assert result.status == "timeout"
        assert result.duration_ms == 3600000
        assert result.engine == "claude-code"
        assert result.error_message is None  # timeout is not a "failure"

    @pytest.mark.asyncio
    async def test_claude_cancelled_returns_cancelled_status(self) -> None:
        """Mock subprocess with cancelled=True produces status='cancelled'."""
        mock_result = _subprocess_cancelled(duration_ms=8000)

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await ClaudeCodeAdapter().run(_make_task())

        assert result.status == "cancelled"
        assert result.duration_ms == 8000
        assert result.engine == "claude-code"
        assert result.error_message is None


class TestClaudeFailure:
    """ClaudeCodeAdapter: non-zero exit codes and error handling."""

    @pytest.mark.asyncio
    async def test_claude_failure_returns_error(self) -> None:
        """Mock subprocess with return_code=1 produces status='failure' with error."""
        mock_result = _subprocess_fail(
            return_code=1,
            stderr="Error: rate limit exceeded",
            duration_ms=2000,
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await ClaudeCodeAdapter().run(_make_task())

        assert result.status == "failure"
        assert result.error_message is not None
        assert "rate limit exceeded" in result.error_message
        assert result.engine == "claude-code"

    @pytest.mark.asyncio
    async def test_claude_failure_still_parses_cost(self) -> None:
        """Even on failure, stdout is parsed for cost metrics."""
        stdout = json.dumps({"cost_usd": 0.08, "num_turns": 3})
        mock_result = SubprocessResult(
            return_code=1,
            stdout=stdout,
            stderr="Process exited with error",
            duration_ms=7000,
            timed_out=False,
            cancelled=False,
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await ClaudeCodeAdapter().run(_make_task())

        assert result.status == "failure"
        assert result.cost_usd == 0.08
        assert result.num_turns == 3


class TestClaudeNoWorkspace:
    """ClaudeCodeAdapter: tasks without workspace_path are rejected."""

    @pytest.mark.asyncio
    async def test_claude_no_workspace_returns_failure(self) -> None:
        """Task without workspace_path set returns immediate failure."""
        task = _make_task_no_workspace()
        adapter = ClaudeCodeAdapter()
        result = await adapter.run(task)

        assert result.status == "failure"
        assert result.error_message is not None
        assert "workspace" in result.error_message.lower()
        assert result.engine == "claude-code"


class TestClaudeCancelEvent:
    """ClaudeCodeAdapter: cancel_event is forwarded to run_engine_subprocess."""

    @pytest.mark.asyncio
    async def test_claude_passes_cancel_event(self) -> None:
        """Verify cancel_event kwarg is passed through to run_engine_subprocess."""
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.01, "num_turns": 1}),
        )
        cancel_event = asyncio.Event()

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task(), cancel_event=cancel_event)

        # Verify cancel_event was passed as a keyword argument
        assert mock_run.call_count == 1
        call_kwargs = mock_run.call_args.kwargs
        assert "cancel_event" in call_kwargs
        assert call_kwargs["cancel_event"] is cancel_event

    @pytest.mark.asyncio
    async def test_claude_passes_none_cancel_event_by_default(self) -> None:
        """Without explicit cancel_event, None is passed."""
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["cancel_event"] is None


class TestClaudeEnvOverrides:
    """ClaudeCodeAdapter: environment variable injection."""

    @pytest.mark.asyncio
    async def test_claude_env_overrides_include_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify ANTHROPIC_API_KEY is injected into env_overrides."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-key-123")
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.05, "num_turns": 2}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_API_KEY"] == "sk-ant-test-key-123"

    @pytest.mark.asyncio
    async def test_claude_env_overrides_include_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify ANTHROPIC_BASE_URL is injected when set."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"

    @pytest.mark.asyncio
    async def test_claude_no_api_key_omits_from_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ANTHROPIC_API_KEY is unset, it is not injected."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert "ANTHROPIC_API_KEY" not in env_overrides

    @pytest.mark.asyncio
    async def test_claude_task_env_vars_are_merged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Task-level env_vars are included alongside injected API keys."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-abc")
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        task = _make_task(env_vars={"CUSTOM_VAR": "custom-value"})
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["CUSTOM_VAR"] == "custom-value"
        assert env_overrides["ANTHROPIC_API_KEY"] == "sk-ant-abc"


    @pytest.mark.asyncio
    async def test_claude_env_overrides_include_auth_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify ANTHROPIC_AUTH_TOKEN is injected when set (for OpenRouter)."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://openrouter.ai/api")
        monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-or-v1-test-key")
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )
        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())
        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_AUTH_TOKEN"] == "sk-or-v1-test-key"
        assert env_overrides["ANTHROPIC_BASE_URL"] == "https://openrouter.ai/api"

    @pytest.mark.asyncio
    async def test_claude_no_auth_token_omits_from_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When ANTHROPIC_AUTH_TOKEN is unset, it is not injected."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )
        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())
        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert "ANTHROPIC_AUTH_TOKEN" not in env_overrides

    @pytest.mark.asyncio
    async def test_claude_bedrock_env_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify CLAUDE_CODE_USE_BEDROCK is forwarded."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )
        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())
        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["CLAUDE_CODE_USE_BEDROCK"] == "1"


class TestClaudeCommandBuilding:
    """ClaudeCodeAdapter: verify the constructed CLI command."""

    @pytest.mark.asyncio
    async def test_claude_uses_task_model(self) -> None:
        """Task model is passed as --model argument."""
        task = _make_task(model="claude-opus-4-6")
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.5, "num_turns": 10}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await ClaudeCodeAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "claude-opus-4-6"
        assert result.model == "claude-opus-4-6"

    @pytest.mark.asyncio
    async def test_claude_default_model_when_none(self) -> None:
        """No model on task defaults to claude-sonnet-4-6."""
        task = _make_task(model=None)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await ClaudeCodeAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "claude-sonnet-4-6"
        assert result.model == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_claude_passes_max_turns(self) -> None:
        """Task max_turns is passed as --max-turns argument."""
        task = _make_task(max_turns=25)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        turns_idx = cmd.index("--max-turns") + 1
        assert cmd[turns_idx] == "25"

    @pytest.mark.asyncio
    async def test_claude_passes_description_as_stdin(self) -> None:
        """Task description is piped via stdin_text."""
        task = _make_task(description="Refactor the auth middleware")
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(task)

        assert mock_run.call_args.kwargs["stdin_text"] == "Refactor the auth middleware"

    @pytest.mark.asyncio
    async def test_claude_passes_workspace_as_cwd(self) -> None:
        """Workspace path is passed as cwd to subprocess."""
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(_make_task())

        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/fake-workspace")

    @pytest.mark.asyncio
    async def test_claude_passes_timeout_seconds(self) -> None:
        """Task timeout_seconds is forwarded to subprocess."""
        task = _make_task(timeout_seconds=1800)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(task)

        assert mock_run.call_args.kwargs["timeout_seconds"] == 1800


# ── AiderAdapter tests ──────────────────────────────────────────────────────

_AIDER_SUBPROCESS = "apps.runner.engines.aider.run_engine_subprocess"


class TestAiderSuccess:
    """AiderAdapter: successful runs and output parsing."""

    @pytest.mark.asyncio
    async def test_aider_success_returns_result(self) -> None:
        """Mock subprocess success produces status='success'."""
        mock_result = _subprocess_ok(
            stdout="Editing file.py\nApplied 3 edits\nDone!",
            duration_ms=25000,
        )

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(
                _make_task(model="deepseek/deepseek-chat")
            )

        assert result.status == "success"
        assert result.engine == "aider"
        assert result.duration_ms == 25000
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_aider_parses_cost_from_stdout(self) -> None:
        """Mock output with 'Cost: $0.05' parses cost correctly."""
        stdout = (
            "Editing auth.py\n"
            "Applied changes to 2 files\n"
            "Tokens: 12.3k sent, 4.5k received. Cost: $0.05"
        )
        mock_result = _subprocess_ok(stdout=stdout)

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(
                _make_task(model="deepseek/deepseek-chat")
            )

        assert result.status == "success"
        assert result.cost_usd == 0.05

    @pytest.mark.asyncio
    async def test_aider_no_cost_in_output_defaults_zero(self) -> None:
        """When stdout has no cost line, cost_usd defaults to 0.0."""
        mock_result = _subprocess_ok(stdout="Applied edits. Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(
                _make_task(model="gpt-4.1")
            )

        assert result.cost_usd == 0.0

    @pytest.mark.asyncio
    async def test_aider_integer_cost_parsed(self) -> None:
        """Integer cost like 'Cost: $2' parses correctly."""
        mock_result = _subprocess_ok(stdout="Tokens: 100k sent. Cost: $2")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(
                _make_task(model="claude-sonnet-4-6")
            )

        assert result.cost_usd == 2.0


class TestAiderTimeoutAndCancel:
    """AiderAdapter: timeout and cancellation scenarios."""

    @pytest.mark.asyncio
    async def test_aider_timeout_returns_timeout_status(self) -> None:
        """Mock subprocess with timed_out=True produces status='timeout'."""
        mock_result = _subprocess_timeout(duration_ms=3600000)

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(
                _make_task(model="gpt-4.1")
            )

        assert result.status == "timeout"
        assert result.duration_ms == 3600000
        assert result.engine == "aider"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_aider_cancelled_returns_cancelled_status(self) -> None:
        """Mock subprocess with cancelled=True produces status='cancelled'."""
        mock_result = _subprocess_cancelled(duration_ms=12000)

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(
                _make_task(model="deepseek-chat")
            )

        assert result.status == "cancelled"
        assert result.duration_ms == 12000
        assert result.engine == "aider"
        assert result.error_message is None


class TestAiderNoWorkspace:
    """AiderAdapter: tasks without workspace_path are rejected."""

    @pytest.mark.asyncio
    async def test_aider_no_workspace_returns_failure(self) -> None:
        """Task without workspace_path set returns immediate failure."""
        task = _make_task_no_workspace()
        result = await AiderAdapter().run(task)

        assert result.status == "failure"
        assert result.error_message is not None
        assert "workspace" in result.error_message.lower()
        assert result.engine == "aider"


class TestAiderCancelEvent:
    """AiderAdapter: cancel_event is forwarded to run_engine_subprocess."""

    @pytest.mark.asyncio
    async def test_aider_passes_cancel_event(self) -> None:
        """Verify cancel_event kwarg is passed through to run_engine_subprocess."""
        mock_result = _subprocess_ok(stdout="Done!")
        cancel_event = asyncio.Event()

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(
                _make_task(model="gpt-4.1"),
                cancel_event=cancel_event,
            )

        assert mock_run.call_count == 1
        call_kwargs = mock_run.call_args.kwargs
        assert "cancel_event" in call_kwargs
        assert call_kwargs["cancel_event"] is cancel_event

    @pytest.mark.asyncio
    async def test_aider_passes_none_cancel_event_by_default(self) -> None:
        """Without explicit cancel_event, None is passed."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(_make_task(model="gpt-4.1"))

        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["cancel_event"] is None


class TestAiderEnvOverrides:
    """AiderAdapter: API key injection based on model prefix."""

    @pytest.mark.asyncio
    async def test_aider_injects_deepseek_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify correct API key for deepseek model."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test-key")
        task = _make_task(model="deepseek/deepseek-chat")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["DEEPSEEK_API_KEY"] == "sk-deepseek-test-key"

    @pytest.mark.asyncio
    async def test_aider_injects_deepseek_dash_prefix(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Models starting with 'deepseek-' also get DEEPSEEK_API_KEY."""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-ds-abc")
        task = _make_task(model="deepseek-chat")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["DEEPSEEK_API_KEY"] == "sk-ds-abc"

    @pytest.mark.asyncio
    async def test_aider_injects_openai_key_for_gpt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GPT models get OPENAI_API_KEY injected."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        task = _make_task(model="gpt-4.1-mini")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENAI_API_KEY"] == "sk-openai-test"

    @pytest.mark.asyncio
    async def test_aider_injects_anthropic_key_for_claude(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Claude models get ANTHROPIC_API_KEY injected."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xyz")
        task = _make_task(model="claude-sonnet-4-6")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_API_KEY"] == "sk-ant-xyz"

    @pytest.mark.asyncio
    async def test_aider_injects_gemini_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Gemini models get GEMINI_API_KEY injected."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
        task = _make_task(model="gemini-2.0-flash")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["GEMINI_API_KEY"] == "AIza-test"

    @pytest.mark.asyncio
    async def test_aider_injects_openrouter_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OpenRouter models get OPENROUTER_API_KEY injected."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
        task = _make_task(model="openrouter/anthropic/claude-3.5-sonnet")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENROUTER_API_KEY"] == "sk-or-test"

    @pytest.mark.asyncio
    async def test_aider_no_api_key_set_omits_from_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the matching API key env var is unset, it is not injected."""
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        task = _make_task(model="deepseek/deepseek-chat")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert "DEEPSEEK_API_KEY" not in env_overrides

    @pytest.mark.asyncio
    async def test_aider_task_env_vars_are_merged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Task-level env_vars are included alongside injected API keys."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-abc")
        task = _make_task(model="gpt-4.1", env_vars={"MY_FLAG": "true"})
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["MY_FLAG"] == "true"
        assert env_overrides["OPENAI_API_KEY"] == "sk-openai-abc"


class TestAiderCommandBuilding:
    """AiderAdapter: verify the constructed CLI command."""

    @pytest.mark.asyncio
    async def test_aider_uses_task_model(self) -> None:
        """Task model is passed as --model argument."""
        task = _make_task(model="deepseek/deepseek-chat")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await AiderAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "deepseek/deepseek-chat"
        assert result.model == "deepseek/deepseek-chat"

    @pytest.mark.asyncio
    async def test_aider_default_model_when_none(self) -> None:
        """No model on task defaults to claude-sonnet-4-6."""
        task = _make_task(model=None)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await AiderAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "claude-sonnet-4-6"
        assert result.model == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_aider_passes_description_as_message(self) -> None:
        """Task description is passed via --message argument."""
        task = _make_task(description="Implement user signup flow")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        msg_idx = cmd.index("--message") + 1
        assert cmd[msg_idx] == "Implement user signup flow"

    @pytest.mark.asyncio
    async def test_aider_includes_yes_always_and_no_git(self) -> None:
        """Aider command includes --yes-always, --no-auto-commits, --no-git."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(_make_task(model="gpt-4.1"))

        cmd = mock_run.call_args.args[0]
        assert "--yes-always" in cmd
        assert "--no-auto-commits" in cmd
        assert "--no-git" in cmd

    @pytest.mark.asyncio
    async def test_aider_includes_no_stream(self) -> None:
        """Aider command includes --no-stream for headless use."""
        mock_result = _subprocess_ok(stdout="Done!")
        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(_make_task(model="gpt-4.1"))
        cmd = mock_run.call_args.args[0]
        assert "--no-stream" in cmd

    @pytest.mark.asyncio
    async def test_aider_passes_workspace_as_cwd(self) -> None:
        """Workspace path is passed as cwd to subprocess."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(_make_task(model="gpt-4.1"))

        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/fake-workspace")

    @pytest.mark.asyncio
    async def test_aider_passes_timeout_seconds(self) -> None:
        """Task timeout_seconds is forwarded to subprocess."""
        task = _make_task(model="gpt-4.1", timeout_seconds=900)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        assert mock_run.call_args.kwargs["timeout_seconds"] == 900


class TestAiderFailure:
    """AiderAdapter: non-zero exit codes and error handling."""

    @pytest.mark.asyncio
    async def test_aider_failure_returns_error(self) -> None:
        """Non-zero exit code produces status='failure' with error."""
        mock_result = _subprocess_fail(
            return_code=1,
            stderr="Error: Model not available",
        )

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(_make_task(model="gpt-4.1"))

        assert result.status == "failure"
        assert result.error_message is not None
        assert "Model not available" in result.error_message

    @pytest.mark.asyncio
    async def test_aider_failure_still_parses_cost(self) -> None:
        """Even on failure, stdout is parsed for cost."""
        mock_result = SubprocessResult(
            return_code=1,
            stdout="Tokens: 5k sent. Cost: $0.03\nFailed to apply edits",
            stderr="Non-zero exit",
            duration_ms=8000,
            timed_out=False,
            cancelled=False,
        )

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await AiderAdapter().run(_make_task(model="gpt-4.1"))

        assert result.status == "failure"
        assert result.cost_usd == 0.03


# ── Sandbox wiring tests ──────────────────────────────────────────────────


class TestClaudeSandboxWiring:
    """ClaudeCodeAdapter: sandbox_mode wraps command in Docker."""

    @pytest.mark.asyncio
    async def test_claude_sandbox_wraps_command(self) -> None:
        """When sandbox_mode=True, cmd starts with 'docker' instead of 'claude'."""
        task = _make_task(sandbox_mode=True, sandbox_image="lailatov/sandbox:python")
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.1, "num_turns": 3}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "lailatov/sandbox:python" in cmd

    @pytest.mark.asyncio
    async def test_claude_no_sandbox_uses_claude_command(self) -> None:
        """When sandbox_mode=False (default), cmd starts with 'claude'."""
        task = _make_task(sandbox_mode=False)
        mock_result = _subprocess_ok(
            stdout=json.dumps({"cost_usd": 0.0, "num_turns": 1}),
        )

        with patch(
            _CLAUDE_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await ClaudeCodeAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "claude"


class TestAiderSandboxWiring:
    """AiderAdapter: sandbox_mode wraps command in Docker."""

    @pytest.mark.asyncio
    async def test_aider_sandbox_wraps_command(self) -> None:
        """When sandbox_mode=True, cmd starts with 'docker' instead of 'aider'."""
        task = _make_task(
            model="gpt-4.1",
            sandbox_mode=True,
            sandbox_image="lailatov/sandbox:node",
        )
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "lailatov/sandbox:node" in cmd

    @pytest.mark.asyncio
    async def test_aider_no_sandbox_uses_aider_command(self) -> None:
        """When sandbox_mode=False (default), cmd starts with 'aider'."""
        task = _make_task(model="gpt-4.1", sandbox_mode=False)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _AIDER_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await AiderAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "aider"


# ── GeminiCliAdapter tests ─────────────────────────────────────────────────

_GEMINI_SUBPROCESS = "apps.runner.engines.gemini_cli.run_engine_subprocess"


class TestGeminiEnvOverrides:
    """GeminiCliAdapter: environment variable injection."""

    @pytest.mark.asyncio
    async def test_gemini_injects_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify GEMINI_API_KEY is injected into env_overrides."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-key-123")
        monkeypatch.delenv("GOOGLE_GEMINI_BASE_URL", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        mock_result = _subprocess_ok(stdout="Generated code", duration_ms=8000)

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["GEMINI_API_KEY"] == "AIza-test-key-123"

    @pytest.mark.asyncio
    async def test_gemini_injects_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify GOOGLE_GEMINI_BASE_URL is injected when set."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
        monkeypatch.setenv("GOOGLE_GEMINI_BASE_URL", "https://my-proxy.example.com")
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        mock_result = _subprocess_ok(stdout="Done")

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["GOOGLE_GEMINI_BASE_URL"] == "https://my-proxy.example.com"

    @pytest.mark.asyncio
    async def test_gemini_no_base_url_omits_from_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When GOOGLE_GEMINI_BASE_URL is unset, it is not injected."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
        monkeypatch.delenv("GOOGLE_GEMINI_BASE_URL", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
        mock_result = _subprocess_ok(stdout="Done")

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert "GOOGLE_GEMINI_BASE_URL" not in env_overrides

    @pytest.mark.asyncio
    async def test_gemini_vertex_env_forwarded(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION are forwarded."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-test")
        monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "my-gcp-project")
        monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        monkeypatch.delenv("GOOGLE_GEMINI_BASE_URL", raising=False)
        mock_result = _subprocess_ok(stdout="Done")

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["GOOGLE_CLOUD_PROJECT"] == "my-gcp-project"
        assert env_overrides["GOOGLE_CLOUD_LOCATION"] == "us-central1"


class TestGeminiCommandBuilding:
    """GeminiCliAdapter: verify the constructed CLI command."""

    @pytest.mark.asyncio
    async def test_gemini_uses_task_model(self) -> None:
        """Task model is passed as --model argument."""
        task = _make_task(model="gemini-2.5-pro")
        mock_result = _subprocess_ok(stdout="Done")

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await GeminiCliAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "gemini-2.5-pro"
        assert result.model == "gemini-2.5-pro"

    @pytest.mark.asyncio
    async def test_gemini_passes_description_as_positional(self) -> None:
        """Task description is passed as a positional argument (not --message)."""
        task = _make_task(description="Refactor the auth middleware")
        mock_result = _subprocess_ok(stdout="Done")

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert "--message" not in cmd
        assert "Refactor the auth middleware" in cmd

    @pytest.mark.asyncio
    async def test_gemini_default_model(self) -> None:
        """No model on task defaults to gemini-2.5-flash."""
        task = _make_task(model=None)
        mock_result = _subprocess_ok(stdout="Done")

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await GeminiCliAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "gemini-2.5-flash"
        assert result.model == "gemini-2.5-flash"


class TestGeminiSuccess:
    """GeminiCliAdapter: successful runs and failure handling."""

    @pytest.mark.asyncio
    async def test_gemini_success_returns_result(self) -> None:
        """Mock subprocess success produces status='success'."""
        mock_result = _subprocess_ok(
            stdout="Generated code for auth module\nDone!",
            duration_ms=20000,
        )

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await GeminiCliAdapter().run(_make_task())

        assert result.status == "success"
        assert result.engine == "gemini-cli"
        assert result.duration_ms == 20000
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_gemini_failure_returns_error(self) -> None:
        """Non-zero exit code produces status='failure' with error."""
        mock_result = _subprocess_fail(
            return_code=1,
            stderr="Error: API key invalid",
            duration_ms=3000,
        )

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await GeminiCliAdapter().run(_make_task())

        assert result.status == "failure"
        assert result.error_message is not None
        assert "API key invalid" in result.error_message
        assert result.engine == "gemini-cli"


class TestGeminiSandboxWiring:
    """GeminiCliAdapter: sandbox_mode wraps command in Docker."""

    @pytest.mark.asyncio
    async def test_gemini_sandbox_wraps_command(self) -> None:
        """When sandbox_mode=True, cmd starts with 'docker' instead of 'gemini'."""
        task = _make_task(
            sandbox_mode=True,
            sandbox_image="lailatov/sandbox:python",
        )
        mock_result = _subprocess_ok(stdout="Done")

        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "lailatov/sandbox:python" in cmd

# ── CodexAdapter tests ──────────────────────────────────────────────────────

_CODEX_SUBPROCESS = "apps.runner.engines.codex.run_engine_subprocess"


class TestCodexEnvOverrides:
    """CodexAdapter: environment variable injection for OpenAI and OpenRouter."""

    @pytest.mark.asyncio
    async def test_codex_injects_openai_api_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify OPENAI_API_KEY is injected into env_overrides."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENAI_API_KEY"] == "sk-test-key"

    @pytest.mark.asyncio
    async def test_codex_injects_openai_base_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify OPENAI_BASE_URL is injected when set (OpenRouter support)."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-or-test")
        monkeypatch.setenv("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENAI_BASE_URL"] == "https://openrouter.ai/api/v1"

    @pytest.mark.asyncio
    async def test_codex_no_base_url_omits_from_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When OPENAI_BASE_URL is unset, it is not injected."""
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert "OPENAI_BASE_URL" not in env_overrides

    @pytest.mark.asyncio
    async def test_codex_no_api_key_omits_from_overrides(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When OPENAI_API_KEY is unset, it is not injected."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert "OPENAI_API_KEY" not in env_overrides

    @pytest.mark.asyncio
    async def test_codex_task_env_vars_are_merged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Task-level env_vars are included alongside injected API keys."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-abc")
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        task = _make_task(env_vars={"CUSTOM_VAR": "custom-value"})
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["CUSTOM_VAR"] == "custom-value"
        assert env_overrides["OPENAI_API_KEY"] == "sk-openai-abc"


class TestCodexCommandBuilding:
    """CodexAdapter: verify the constructed CLI command."""

    @pytest.mark.asyncio
    async def test_codex_uses_exec_subcommand(self) -> None:
        """Command uses ``exec`` subcommand for non-interactive mode."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task())

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "codex"
        assert cmd[1] == "exec"

    @pytest.mark.asyncio
    async def test_codex_includes_full_auto_flag(self) -> None:
        """Command includes --full-auto for headless execution."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task())

        cmd = mock_run.call_args.args[0]
        assert "--full-auto" in cmd

    @pytest.mark.asyncio
    async def test_codex_uses_task_model(self) -> None:
        """Task model is passed as --model argument."""
        task = _make_task(model="o3-mini")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await CodexAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "o3-mini"
        assert result.model == "o3-mini"

    @pytest.mark.asyncio
    async def test_codex_default_model_when_none(self) -> None:
        """No model on task defaults to gpt-4.1."""
        task = _make_task(model=None)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await CodexAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "gpt-4.1-mini"
        assert result.model == "gpt-4.1-mini"

    @pytest.mark.asyncio
    async def test_codex_passes_description_as_positional_arg(self) -> None:
        """Task description is passed as positional argument to exec."""
        task = _make_task(description="Refactor the auth module")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[-1] == "Refactor the auth module"

    @pytest.mark.asyncio
    async def test_codex_passes_workspace_as_cwd(self) -> None:
        """Workspace path is passed as cwd to subprocess."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task())

        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/fake-workspace")


# ── PiAdapter tests ─────────────────────────────────────────────────────────

_PI_SUBPROCESS = "apps.runner.engines.pi.run_engine_subprocess"


class TestPiCommandBuilding:
    """PiAdapter: verify the constructed CLI command includes --model, --print, --no-session."""

    @pytest.mark.asyncio
    async def test_pi_includes_model_flag(self) -> None:
        """Task model is passed as --model argument."""
        task = _make_task(model="gpt-4.1")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await PiAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "gpt-4.1"
        assert result.model == "gpt-4.1"

    @pytest.mark.asyncio
    async def test_pi_default_model_when_none(self) -> None:
        """No model on task defaults to claude-sonnet-4-6."""
        task = _make_task(model=None)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await PiAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "claude-sonnet-4-6"
        assert result.model == "claude-sonnet-4-6"

    @pytest.mark.asyncio
    async def test_pi_includes_print_flag(self) -> None:
        """Command includes --print for headless output."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        cmd = mock_run.call_args.args[0]
        assert "--print" in cmd

    @pytest.mark.asyncio
    async def test_pi_includes_no_session_flag(self) -> None:
        """Command includes --no-session for stateless execution."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        cmd = mock_run.call_args.args[0]
        assert "--no-session" in cmd

    @pytest.mark.asyncio
    async def test_pi_passes_description_as_positional_arg(self) -> None:
        """Task description is passed as the last positional argument."""
        task = _make_task(description="Refactor the parser")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[-1] == "Refactor the parser"

    @pytest.mark.asyncio
    async def test_pi_passes_workspace_as_cwd(self) -> None:
        """Workspace path is passed as cwd to subprocess."""
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/fake-workspace")

    @pytest.mark.asyncio
    async def test_pi_passes_timeout_seconds(self) -> None:
        """Task timeout_seconds is forwarded to subprocess."""
        task = _make_task(timeout_seconds=1200)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(task)

        assert mock_run.call_args.kwargs["timeout_seconds"] == 1200


class TestPiEnvOverrides:
    """PiAdapter: all 6 provider API keys are injected when set."""

    @pytest.mark.asyncio
    async def test_pi_injects_anthropic_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify ANTHROPIC_API_KEY is injected."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-pi-test")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_API_KEY"] == "sk-ant-pi-test"

    @pytest.mark.asyncio
    async def test_pi_injects_openai_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify OPENAI_API_KEY is injected."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-pi-test")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENAI_API_KEY"] == "sk-openai-pi-test"

    @pytest.mark.asyncio
    async def test_pi_injects_gemini_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify GEMINI_API_KEY is injected."""
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-pi-test")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["GEMINI_API_KEY"] == "AIza-pi-test"

    @pytest.mark.asyncio
    async def test_pi_injects_openrouter_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify OPENROUTER_API_KEY is injected."""
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-pi-test")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENROUTER_API_KEY"] == "sk-or-pi-test"

    @pytest.mark.asyncio
    async def test_pi_injects_groq_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify GROQ_API_KEY is injected."""
        monkeypatch.setenv("GROQ_API_KEY", "gsk-pi-test")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["GROQ_API_KEY"] == "gsk-pi-test"

    @pytest.mark.asyncio
    async def test_pi_injects_mistral_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify MISTRAL_API_KEY is injected."""
        monkeypatch.setenv("MISTRAL_API_KEY", "sk-mistral-pi-test")
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["MISTRAL_API_KEY"] == "sk-mistral-pi-test"

    @pytest.mark.asyncio
    async def test_pi_all_six_keys_injected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify all 6 provider keys are injected when all are set."""
        keys = {
            "ANTHROPIC_API_KEY": "sk-ant",
            "OPENAI_API_KEY": "sk-oai",
            "GEMINI_API_KEY": "AIza",
            "OPENROUTER_API_KEY": "sk-or",
            "GROQ_API_KEY": "gsk",
            "MISTRAL_API_KEY": "sk-mis",
        }
        for k, v in keys.items():
            monkeypatch.setenv(k, v)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        for k, v in keys.items():
            assert env_overrides[k] == v

    @pytest.mark.asyncio
    async def test_pi_unset_key_omitted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When a provider key is unset, it is not injected."""
        for k in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
            "GROQ_API_KEY",
            "MISTRAL_API_KEY",
        ):
            monkeypatch.delenv(k, raising=False)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task())

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        for k in (
            "ANTHROPIC_API_KEY",
            "OPENAI_API_KEY",
            "GEMINI_API_KEY",
            "OPENROUTER_API_KEY",
            "GROQ_API_KEY",
            "MISTRAL_API_KEY",
        ):
            assert k not in env_overrides

    @pytest.mark.asyncio
    async def test_pi_task_env_vars_are_merged(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Task-level env_vars are included alongside injected API keys."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-merge")
        task = _make_task(env_vars={"MY_CUSTOM": "value"})
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(task)

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["MY_CUSTOM"] == "value"
        assert env_overrides["ANTHROPIC_API_KEY"] == "sk-ant-merge"


class TestPiSuccess:
    """PiAdapter: basic success, failure, timeout, and cancel scenarios."""

    @pytest.mark.asyncio
    async def test_pi_success_returns_result(self) -> None:
        """Mock subprocess success produces status='success'."""
        mock_result = _subprocess_ok(stdout="Edits applied!", duration_ms=20000)

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await PiAdapter().run(_make_task())

        assert result.status == "success"
        assert result.engine == "oh-my-pi"
        assert result.duration_ms == 20000
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_pi_failure_returns_error(self) -> None:
        """Non-zero exit code produces status='failure' with error."""
        mock_result = _subprocess_fail(
            return_code=1,
            stderr="Error: model not found",
        )

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await PiAdapter().run(_make_task())

        assert result.status == "failure"
        assert result.error_message is not None
        assert "model not found" in result.error_message

    @pytest.mark.asyncio
    async def test_pi_timeout_returns_timeout_status(self) -> None:
        """Mock subprocess with timed_out=True produces status='timeout'."""
        mock_result = _subprocess_timeout(duration_ms=3600000)

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await PiAdapter().run(_make_task())

        assert result.status == "timeout"
        assert result.duration_ms == 3600000
        assert result.engine == "oh-my-pi"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_pi_cancelled_returns_cancelled_status(self) -> None:
        """Mock subprocess with cancelled=True produces status='cancelled'."""
        mock_result = _subprocess_cancelled(duration_ms=9000)

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await PiAdapter().run(_make_task())

        assert result.status == "cancelled"
        assert result.duration_ms == 9000
        assert result.engine == "oh-my-pi"
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_pi_passes_cancel_event(self) -> None:
        """Verify cancel_event kwarg is passed through to run_engine_subprocess."""
        mock_result = _subprocess_ok(stdout="Done!")
        cancel_event = asyncio.Event()

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(_make_task(), cancel_event=cancel_event)

        assert mock_run.call_count == 1
        call_kwargs = mock_run.call_args.kwargs
        assert "cancel_event" in call_kwargs
        assert call_kwargs["cancel_event"] is cancel_event


class TestPiNoWorkspace:
    """PiAdapter: tasks without workspace_path are rejected."""

    @pytest.mark.asyncio
    async def test_pi_no_workspace_returns_failure(self) -> None:
        """Task without workspace_path set returns immediate failure."""
        task = _make_task_no_workspace()
        result = await PiAdapter().run(task)

        assert result.status == "failure"
        assert result.error_message is not None
        assert "workspace" in result.error_message.lower()
        assert result.engine == "oh-my-pi"


class TestPiSandboxWiring:
    """PiAdapter: sandbox_mode wraps command in Docker."""

    @pytest.mark.asyncio
    async def test_pi_sandbox_wraps_command(self) -> None:
        """When sandbox_mode=True, cmd starts with 'docker' instead of 'omp'."""
        task = _make_task(
            sandbox_mode=True,
            sandbox_image="lailatov/sandbox:python",
        )
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "lailatov/sandbox:python" in cmd

    @pytest.mark.asyncio
    async def test_pi_no_sandbox_uses_omp_command(self) -> None:
        """When sandbox_mode=False (default), cmd starts with 'omp'."""
        task = _make_task(sandbox_mode=False)
        mock_result = _subprocess_ok(stdout="Done!")

        with patch(
            _PI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await PiAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "omp"

