"""Tests for GeminiCliAdapter — wraps the gemini CLI."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.runner.engines.gemini_cli import GeminiCliAdapter
from apps.runner.engines.protocol import AgentEngine
from apps.runner.engines.subprocess_util import SubprocessResult
from apps.runner.models import RunnerTask


def _make_task(**overrides: object) -> RunnerTask:
    defaults: dict[str, object] = {
        "task_id": "test-gemini-1",
        "repo_url": "https://github.com/org/repo",
        "branch": "agent/test-1",
        "base_branch": "main",
        "description": "Optimize the search query",
    }
    defaults.update(overrides)
    task = RunnerTask(**defaults)
    object.__setattr__(task, "workspace_path", Path("/tmp/fake-workspace"))
    return task


_GEMINI_SUBPROCESS = (
    "apps.runner.engines.gemini_cli.run_engine_subprocess"
)


class TestGeminiProtocol:
    def test_gemini_is_agent_engine(self) -> None:
        assert isinstance(GeminiCliAdapter(), AgentEngine)

    def test_gemini_name(self) -> None:
        assert GeminiCliAdapter().name == "gemini-cli"

    def test_gemini_supported_models(self) -> None:
        models = GeminiCliAdapter().supported_models
        assert "gemini-2.5-pro" in models
        assert "gemini-2.5-flash" in models


class TestGeminiSuccess:
    @pytest.mark.asyncio
    async def test_gemini_success_returns_result(self) -> None:
        mock_result = SubprocessResult(
            return_code=0, stdout="Applied changes to 2 files",
            stderr="", duration_ms=20000,
            timed_out=False, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await GeminiCliAdapter().run(
                _make_task(model="gemini-2.5-pro"),
            )
        assert result.status == "success"
        assert result.engine == "gemini-cli"
        assert result.model == "gemini-2.5-pro"
        assert result.duration_ms == 20000

    @pytest.mark.asyncio
    async def test_gemini_default_model(self) -> None:
        mock_result = SubprocessResult(
            return_code=0, stdout="Done", stderr="",
            duration_ms=5000, timed_out=False, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            result = await GeminiCliAdapter().run(
                _make_task(model=None),
            )
        cmd = mock_run.call_args.args[0]
        model_idx = cmd.index("--model") + 1
        assert cmd[model_idx] == "gemini-2.5-flash"
        assert result.model == "gemini-2.5-flash"


class TestGeminiFailure:
    @pytest.mark.asyncio
    async def test_gemini_failure_returns_error(self) -> None:
        mock_result = SubprocessResult(
            return_code=1, stdout="",
            stderr="Error: quota exceeded",
            duration_ms=2000, timed_out=False, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await GeminiCliAdapter().run(
                _make_task(model="gemini-2.5-pro"),
            )
        assert result.status == "failure"
        assert "quota exceeded" in result.error_message


class TestGeminiTimeout:
    @pytest.mark.asyncio
    async def test_gemini_timeout(self) -> None:
        mock_result = SubprocessResult(
            return_code=-9, stdout="", stderr="timeout",
            duration_ms=3600000, timed_out=True, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await GeminiCliAdapter().run(
                _make_task(model="gemini-2.5-pro"),
            )
        assert result.status == "timeout"


class TestGeminiCancel:
    @pytest.mark.asyncio
    async def test_gemini_cancelled(self) -> None:
        mock_result = SubprocessResult(
            return_code=-15, stdout="", stderr="cancelled",
            duration_ms=5000, timed_out=False, cancelled=True,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            result = await GeminiCliAdapter().run(
                _make_task(model="gemini-2.5-pro"),
            )
        assert result.status == "cancelled"

    @pytest.mark.asyncio
    async def test_gemini_passes_cancel_event(self) -> None:
        mock_result = SubprocessResult(
            return_code=0, stdout="Done", stderr="",
            duration_ms=5000, timed_out=False, cancelled=False,
        )
        cancel_event = asyncio.Event()
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(
                _make_task(model="gemini-2.5-pro"),
                cancel_event=cancel_event,
            )
        assert mock_run.call_args.kwargs["cancel_event"] is cancel_event


class TestGeminiNoWorkspace:
    @pytest.mark.asyncio
    async def test_gemini_no_workspace_returns_failure(self) -> None:
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b", base_branch="main", description="desc",
        )
        result = await GeminiCliAdapter().run(task)
        assert result.status == "failure"
        assert "workspace" in result.error_message.lower()


class TestGeminiEnv:
    @pytest.mark.asyncio
    async def test_gemini_injects_api_key(
        self, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("GEMINI_API_KEY", "AIza-test-key")
        mock_result = SubprocessResult(
            return_code=0, stdout="Done", stderr="",
            duration_ms=5000, timed_out=False, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(
                _make_task(model="gemini-2.5-pro"),
            )
        env_overrides = mock_run.call_args.kwargs["env_overrides"]
        assert env_overrides["GEMINI_API_KEY"] == "AIza-test-key"


class TestGeminiSandbox:
    @pytest.mark.asyncio
    async def test_gemini_sandbox_wraps_docker(self) -> None:
        task = _make_task(
            model="gemini-2.5-pro",
            sandbox_mode=True,
            sandbox_image="lailatov/sandbox:python",
        )
        mock_result = SubprocessResult(
            return_code=0, stdout="Done", stderr="",
            duration_ms=5000, timed_out=False, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(task)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker"

    @pytest.mark.asyncio
    async def test_gemini_no_sandbox_uses_gemini(self) -> None:
        task = _make_task(model="gemini-2.5-pro", sandbox_mode=False)
        mock_result = SubprocessResult(
            return_code=0, stdout="Done", stderr="",
            duration_ms=5000, timed_out=False, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(task)
        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "gemini"


class TestGeminiCommand:
    @pytest.mark.asyncio
    async def test_gemini_passes_workspace_as_cwd(self) -> None:
        mock_result = SubprocessResult(
            return_code=0, stdout="Done", stderr="",
            duration_ms=5000, timed_out=False, cancelled=False,
        )
        with patch(
            _GEMINI_SUBPROCESS,
            new_callable=AsyncMock,
            return_value=mock_result,
        ) as mock_run:
            await GeminiCliAdapter().run(
                _make_task(model="gemini-2.5-pro"),
            )
        assert mock_run.call_args.kwargs["cwd"] == Path(
            "/tmp/fake-workspace",
        )
