"""Tests for CodexAdapter -- wraps the codex CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.runner.engines.codex import CodexAdapter
from apps.runner.engines.protocol import AgentEngine
from apps.runner.engines.subprocess_util import SubprocessResult
from apps.runner.models import RunnerTask


def _make_task(**overrides: object) -> RunnerTask:
    """Build a RunnerTask with workspace_path pre-set for engine tests."""
    defaults: dict[str, object] = {
        "task_id": "test-codex-1",
        "repo_url": "https://github.com/org/repo",
        "branch": "agent/test-1",
        "base_branch": "main",
        "description": "Fix the login bug",
    }
    defaults.update(overrides)
    task = RunnerTask(**defaults)  # type: ignore[arg-type]
    object.__setattr__(task, "workspace_path", Path("/tmp/fake-workspace"))
    return task


_CODEX_SUBPROCESS = "apps.runner.engines.codex.run_engine_subprocess"


class TestCodexProtocol:
    """CodexAdapter satisfies the AgentEngine protocol."""

    def test_codex_is_agent_engine(self) -> None:
        """CodexAdapter is recognized as AgentEngine via structural subtyping."""
        assert isinstance(CodexAdapter(), AgentEngine)

    def test_codex_name(self) -> None:
        """Engine name is 'codex'."""
        assert CodexAdapter().name == "codex"

    def test_codex_supported_models(self) -> None:
        """Supported models include gpt-4.1 and o3."""
        models = CodexAdapter().supported_models
        assert "gpt-4.1" in models
        assert "o3" in models


class TestCodexSuccess:
    """CodexAdapter: successful runs."""

    @pytest.mark.asyncio
    async def test_codex_success_returns_result(self) -> None:
        """Mock subprocess success produces status='success'."""
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Applied changes to 3 files",
            stderr="",
            duration_ms=30000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await CodexAdapter().run(_make_task(model="gpt-4.1"))

        assert result.status == "success"
        assert result.engine == "codex"
        assert result.model == "gpt-4.1"
        assert result.duration_ms == 30000

    @pytest.mark.asyncio
    async def test_codex_default_model(self) -> None:
        """No model on task defaults to gpt-4.1-mini."""
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await CodexAdapter().run(_make_task(model=None))

        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "gpt-4.1-mini"
        assert result.model == "gpt-4.1-mini"


class TestCodexFailure:
    """CodexAdapter: non-zero exit codes and error handling."""

    @pytest.mark.asyncio
    async def test_codex_failure_returns_error(self) -> None:
        """Non-zero exit code produces status='failure' with error."""
        mock_result = SubprocessResult(
            return_code=1,
            stdout="",
            stderr="Error: rate limit",
            duration_ms=2000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await CodexAdapter().run(_make_task(model="gpt-4.1"))

        assert result.status == "failure"
        assert result.error_message is not None
        assert "rate limit" in result.error_message


class TestCodexTimeout:
    """CodexAdapter: timeout scenarios."""

    @pytest.mark.asyncio
    async def test_codex_timeout(self) -> None:
        """Mock subprocess with timed_out=True produces status='timeout'."""
        mock_result = SubprocessResult(
            return_code=-9,
            stdout="",
            stderr="timeout",
            duration_ms=3600000,
            timed_out=True,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await CodexAdapter().run(_make_task(model="gpt-4.1"))

        assert result.status == "timeout"


class TestCodexCancel:
    """CodexAdapter: cancellation scenarios."""

    @pytest.mark.asyncio
    async def test_codex_cancelled(self) -> None:
        """Mock subprocess with cancelled=True produces status='cancelled'."""
        mock_result = SubprocessResult(
            return_code=-15,
            stdout="",
            stderr="cancelled",
            duration_ms=5000,
            timed_out=False,
            cancelled=True,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await CodexAdapter().run(_make_task(model="gpt-4.1"))

        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_codex_passes_cancel_event(self) -> None:
        """Verify cancel_event kwarg is passed through to run_engine_subprocess."""
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        cancel_event = asyncio.Event()
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(
                _make_task(model="gpt-4.1"),
                cancel_event=cancel_event,
            )

        assert mock_run.call_args.kwargs["cancel_event"] is cancel_event


class TestCodexNoWorkspace:
    """CodexAdapter: tasks without workspace_path are rejected."""

    @pytest.mark.asyncio
    async def test_codex_no_workspace_returns_failure(self) -> None:
        """Task without workspace_path set returns immediate failure."""
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        result = await CodexAdapter().run(task)

        assert result.status == "failure"
        assert result.error_message is not None
        assert "workspace" in result.error_message.lower()


class TestCodexEnv:
    """CodexAdapter: environment variable injection."""

    @pytest.mark.asyncio
    async def test_codex_injects_openai_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify OPENAI_API_KEY is injected into env_overrides."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task(model="gpt-4.1"))

        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENAI_API_KEY"] == "sk-test-key"


class TestCodexSandbox:
    """CodexAdapter: sandbox_mode wraps command in Docker."""

    @pytest.mark.asyncio
    async def test_codex_sandbox_wraps_docker(self) -> None:
        """When sandbox_mode=True, cmd starts with 'docker' instead of 'codex'."""
        task = _make_task(
            model="gpt-4.1",
            sandbox_mode=True,
            sandbox_image="lailatov/sandbox:python",
        )
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker"

    @pytest.mark.asyncio
    async def test_codex_no_sandbox_uses_codex(self) -> None:
        """When sandbox_mode=False (default), cmd starts with 'codex'."""
        task = _make_task(model="gpt-4.1", sandbox_mode=False)
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "codex"


class TestCodexCommand:
    """CodexAdapter: verify the constructed CLI command."""

    @pytest.mark.asyncio
    async def test_codex_command_uses_exec_subcommand(self) -> None:
        """Codex command uses ``exec`` subcommand for non-interactive mode."""
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task(model="gpt-4.1"))

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "codex"
        assert cmd[1] == "exec"

    @pytest.mark.asyncio
    async def test_codex_passes_workspace_as_cwd(self) -> None:
        """Workspace path is passed as cwd to subprocess."""
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _CODEX_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await CodexAdapter().run(_make_task(model="gpt-4.1"))

        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/fake-workspace")
