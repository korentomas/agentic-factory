"""Tests for sandbox integration in engine adapters.

Verifies that ClaudeCodeAdapter and AiderAdapter correctly wrap commands
with Docker when ``task.sandbox_mode`` is True, and pass commands
directly when ``sandbox_mode`` is False.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from apps.runner.engines.aider import AiderAdapter
from apps.runner.engines.claude_code import ClaudeCodeAdapter
from apps.runner.engines.subprocess_util import SubprocessResult
from apps.runner.models import RunnerTask

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_task(**overrides: object) -> RunnerTask:
    """Create a RunnerTask with workspace_path set for engine tests."""
    defaults: dict[str, object] = {
        "task_id": "sandbox-test-1",
        "repo_url": "https://github.com/org/repo",
        "branch": "agent/sandbox-test",
        "base_branch": "main",
        "description": "Fix the bug in sandbox",
    }
    defaults.update(overrides)
    task = RunnerTask(**defaults)  # type: ignore[arg-type]
    # RunnerTask is frozen, so we use object.__setattr__ to set workspace_path
    object.__setattr__(task, "workspace_path", Path("/tmp/fake-workspace"))
    return task


def _success_result() -> SubprocessResult:
    """Standard success subprocess result."""
    return SubprocessResult(
        return_code=0,
        stdout=json.dumps({"cost_usd": 0.05, "num_turns": 3}),
        stderr="",
        duration_ms=10000,
        timed_out=False,
    )


def _aider_success_result() -> SubprocessResult:
    """Standard success subprocess result for aider."""
    return SubprocessResult(
        return_code=0,
        stdout="Tokens: 5k sent. Cost: $0.02\nDone!",
        stderr="",
        duration_ms=8000,
        timed_out=False,
    )


# ── ClaudeCodeAdapter sandbox integration ────────────────────────────────────


class TestClaudeCodeSandboxIntegration:
    """Verify ClaudeCodeAdapter wraps commands with Docker when sandbox_mode=True."""

    @pytest.mark.asyncio
    async def test_sandbox_disabled_passes_cmd_directly(self) -> None:
        """When sandbox_mode=False, cmd should NOT be wrapped in Docker."""
        task = _make_task(sandbox_mode=False)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "claude", "Command should start with 'claude', not 'docker'"
        assert "docker" not in cmd

    @pytest.mark.asyncio
    async def test_sandbox_enabled_wraps_with_docker(self) -> None:
        """When sandbox_mode=True, cmd should be wrapped in Docker."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker", "Command should start with 'docker'"
        assert "run" in cmd
        assert "--rm" in cmd
        # Inner command should be at the end
        assert "claude" in cmd
        assert "--print" in cmd

    @pytest.mark.asyncio
    async def test_sandbox_uses_task_image(self) -> None:
        """Custom sandbox_image from task should be used in Docker command."""
        custom_image = "custom/sandbox:v2"
        task = _make_task(sandbox_mode=True, sandbox_image=custom_image)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert custom_image in cmd, f"Custom image '{custom_image}' not found in cmd"

    @pytest.mark.asyncio
    async def test_sandbox_mounts_workspace(self) -> None:
        """Docker command should mount the workspace directory."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        v_idx = cmd.index("-v")
        mount_arg = cmd[v_idx + 1]
        assert "/tmp/fake-workspace" in mount_arg
        assert ":/workspace" in mount_arg

    @pytest.mark.asyncio
    async def test_sandbox_passes_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Environment variables should be passed as -e flags in Docker cmd."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-sandbox-test")
        monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        # Find all -e flags
        env_flags = []
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd):
                env_flags.append(cmd[i + 1])

        # At least the API key should be passed via -e
        api_key_flags = [f for f in env_flags if f.startswith("ANTHROPIC_API_KEY=")]
        assert len(api_key_flags) == 1, "ANTHROPIC_API_KEY should be passed via -e"
        assert api_key_flags[0] == "ANTHROPIC_API_KEY=sk-ant-sandbox-test"

    @pytest.mark.asyncio
    async def test_sandbox_cwd_remains_host_path(self) -> None:
        """Even in sandbox mode, subprocess cwd should be the host workspace path."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        cwd = mock_run.call_args.kwargs["cwd"]
        assert cwd == Path("/tmp/fake-workspace")

    @pytest.mark.asyncio
    async def test_sandbox_result_still_parsed(self) -> None:
        """Even with sandbox wrapping, the result should be parsed correctly."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ):
            adapter = ClaudeCodeAdapter()
            result = await adapter.run(task)

        assert result.status == "success"
        assert result.cost_usd == 0.05
        assert result.num_turns == 3

    @pytest.mark.asyncio
    async def test_sandbox_network_isolation(self) -> None:
        """Docker command should include network=none for isolation."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.claude_code.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_success_result(),
        ) as mock_run:
            adapter = ClaudeCodeAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert "--network=none" in cmd


# ── AiderAdapter sandbox integration ─────────────────────────────────────────


class TestAiderSandboxIntegration:
    """Verify AiderAdapter wraps commands with Docker when sandbox_mode=True."""

    @pytest.mark.asyncio
    async def test_sandbox_disabled_passes_cmd_directly(self) -> None:
        """When sandbox_mode=False, cmd should NOT be wrapped in Docker."""
        task = _make_task(sandbox_mode=False)

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "aider", "Command should start with 'aider', not 'docker'"
        assert "docker" not in cmd

    @pytest.mark.asyncio
    async def test_sandbox_enabled_wraps_with_docker(self) -> None:
        """When sandbox_mode=True, cmd should be wrapped in Docker."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert cmd[0] == "docker", "Command should start with 'docker'"
        assert "run" in cmd
        assert "--rm" in cmd
        # Inner command should be at the end
        assert "aider" in cmd
        assert "--yes-always" in cmd

    @pytest.mark.asyncio
    async def test_sandbox_uses_task_image(self) -> None:
        """Custom sandbox_image from task should be used in Docker command."""
        custom_image = "lailatov/sandbox:aider-custom"
        task = _make_task(sandbox_mode=True, sandbox_image=custom_image)

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert custom_image in cmd, f"Custom image '{custom_image}' not found in cmd"

    @pytest.mark.asyncio
    async def test_sandbox_mounts_workspace(self) -> None:
        """Docker command should mount the workspace directory."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        v_idx = cmd.index("-v")
        mount_arg = cmd[v_idx + 1]
        assert "/tmp/fake-workspace" in mount_arg
        assert ":/workspace" in mount_arg

    @pytest.mark.asyncio
    async def test_sandbox_passes_env_vars(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Task env_vars should be passed as -e flags in Docker cmd."""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-sandbox")
        task = _make_task(
            sandbox_mode=True,
            model="gpt-4.1",
            env_vars={"CUSTOM_VAR": "custom_value"},
        )

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        # Find all -e flags
        env_flags = []
        for i, arg in enumerate(cmd):
            if arg == "-e" and i + 1 < len(cmd):
                env_flags.append(cmd[i + 1])

        # Custom env var should be present
        custom_flags = [f for f in env_flags if f.startswith("CUSTOM_VAR=")]
        assert len(custom_flags) == 1
        assert custom_flags[0] == "CUSTOM_VAR=custom_value"

        # API key should be passed too
        api_flags = [f for f in env_flags if f.startswith("OPENAI_API_KEY=")]
        assert len(api_flags) == 1

    @pytest.mark.asyncio
    async def test_sandbox_cwd_remains_host_path(self) -> None:
        """Even in sandbox mode, subprocess cwd should be the host workspace path."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        cwd = mock_run.call_args.kwargs["cwd"]
        assert cwd == Path("/tmp/fake-workspace")

    @pytest.mark.asyncio
    async def test_sandbox_result_still_parsed(self) -> None:
        """Even with sandbox wrapping, the result should be parsed correctly."""
        task = _make_task(sandbox_mode=True)

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ):
            adapter = AiderAdapter()
            result = await adapter.run(task)

        assert result.status == "success"
        assert result.cost_usd == 0.02

    @pytest.mark.asyncio
    async def test_sandbox_default_image(self) -> None:
        """Default sandbox_image should be 'lailatov/sandbox:python'."""
        task = _make_task(sandbox_mode=True)
        # Not specifying sandbox_image, so it uses the default

        with patch(
            "apps.runner.engines.aider.run_engine_subprocess",
            new_callable=AsyncMock,
            return_value=_aider_success_result(),
        ) as mock_run:
            adapter = AiderAdapter()
            await adapter.run(task)

        cmd = mock_run.call_args.args[0]
        assert "lailatov/sandbox:python" in cmd
