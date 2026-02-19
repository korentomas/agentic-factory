"""Tests for PiAdapter — wraps the omp (oh-my-pi) CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.runner.engines.pi import PiAdapter
from apps.runner.engines.protocol import AgentEngine
from apps.runner.engines.subprocess_util import SubprocessResult
from apps.runner.models import RunnerTask


def _make_task(**overrides: object) -> RunnerTask:
    defaults: dict[str, object] = {
        "task_id": "test-pi-1",
        "repo_url": "https://github.com/org/repo",
        "branch": "agent/test-1",
        "base_branch": "main",
        "description": "Fix the search indexing bug",
    }
    defaults.update(overrides)
    task = RunnerTask(**defaults)
    object.__setattr__(task, "workspace_path", Path("/tmp/fake-workspace"))
    return task


_PI_SUBPROCESS = "apps.runner.engines.pi.run_engine_subprocess"


class TestPiProtocol:
    def test_pi_is_agent_engine(self) -> None:
        assert isinstance(PiAdapter(), AgentEngine)

    def test_pi_name(self) -> None:
        assert PiAdapter().name == "oh-my-pi"

    def test_pi_supported_models_is_wildcard(self) -> None:
        """oh-my-pi is multi-provider — supports any model."""
        assert PiAdapter().supported_models == ["*"]


class TestPiSuccess:
    @pytest.mark.asyncio
    async def test_pi_success_returns_result(self) -> None:
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Applied changes to 3 files",
            stderr="",
            duration_ms=25000,
            timed_out=False,
            cancelled=False,
        )
        with patch(_PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result):
            result = await PiAdapter().run(_make_task(model="claude-sonnet-4-6"))
        assert result.status == "success"
        assert result.engine == "oh-my-pi"
        assert result.model == "claude-sonnet-4-6"
        assert result.duration_ms == 25000

    @pytest.mark.asyncio
    async def test_pi_default_model(self) -> None:
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(_PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result):
            result = await PiAdapter().run(_make_task(model=None))
        assert result.model == "claude-sonnet-4-6"


class TestPiFailure:
    @pytest.mark.asyncio
    async def test_pi_failure_returns_error(self) -> None:
        mock_result = SubprocessResult(
            return_code=1,
            stdout="",
            stderr="Error: API key not set",
            duration_ms=2000,
            timed_out=False,
            cancelled=False,
        )
        with patch(_PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result):
            result = await PiAdapter().run(_make_task(model="gpt-4.1"))
        assert result.status == "failure"
        assert "API key not set" in result.error_message


class TestPiTimeout:
    @pytest.mark.asyncio
    async def test_pi_timeout(self) -> None:
        mock_result = SubprocessResult(
            return_code=-9,
            stdout="",
            stderr="timeout",
            duration_ms=3600000,
            timed_out=True,
            cancelled=False,
        )
        with patch(_PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result):
            result = await PiAdapter().run(_make_task(model="gpt-4.1"))
        assert result.status == "timeout"


class TestPiCancel:
    @pytest.mark.asyncio
    async def test_pi_cancelled(self) -> None:
        mock_result = SubprocessResult(
            return_code=-15,
            stdout="",
            stderr="cancelled",
            duration_ms=5000,
            timed_out=False,
            cancelled=True,
        )
        with patch(_PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result):
            result = await PiAdapter().run(_make_task(model="gpt-4.1"))
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_pi_passes_cancel_event(self) -> None:
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
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(
                _make_task(model="gpt-4.1"), cancel_event=cancel_event
            )
        assert mock_run.call_args.kwargs["cancel_event"] is cancel_event


class TestPiNoWorkspace:
    @pytest.mark.asyncio
    async def test_pi_no_workspace_returns_failure(self) -> None:
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        result = await PiAdapter().run(task)
        assert result.status == "failure"
        assert "workspace" in result.error_message.lower()


class TestPiEnv:
    @pytest.mark.asyncio
    async def test_pi_injects_anthropic_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(_make_task(model="claude-sonnet-4-6"))
        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["ANTHROPIC_API_KEY"] == "sk-ant-test"

    @pytest.mark.asyncio
    async def test_pi_injects_openai_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(_make_task(model="gpt-4.1"))
        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["OPENAI_API_KEY"] == "sk-openai-test"


class TestPiSandbox:
    @pytest.mark.asyncio
    async def test_pi_sandbox_wraps_docker(self) -> None:
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
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(task)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker"

    @pytest.mark.asyncio
    async def test_pi_no_sandbox_uses_omp(self) -> None:
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
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(task)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "omp"


class TestPiCommand:
    @pytest.mark.asyncio
    async def test_pi_command_has_no_session_flag(self) -> None:
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(_make_task(model="gpt-4.1"))
        cmd = mock_run.call_args.args[0]
        assert "--no-session" in cmd

    @pytest.mark.asyncio
    async def test_pi_passes_workspace_as_cwd(self) -> None:
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(_make_task(model="gpt-4.1"))
        assert mock_run.call_args.kwargs["cwd"] == Path("/tmp/fake-workspace")

    @pytest.mark.asyncio
    async def test_pi_passes_description_as_positional_arg(self) -> None:
        task = _make_task(description="Refactor the auth middleware")
        mock_result = SubprocessResult(
            return_code=0,
            stdout="Done",
            stderr="",
            duration_ms=5000,
            timed_out=False,
            cancelled=False,
        )
        with patch(
            _PI_SUBPROCESS, new_callable=AsyncMock, return_value=mock_result
        ) as mock_run:
            await PiAdapter().run(task)
        cmd = mock_run.call_args.args[0]
        assert "Refactor the auth middleware" in cmd
