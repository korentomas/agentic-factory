"""
Claude Code engine adapter.

Wraps the ``claude`` CLI in ``--print`` mode for headless execution.
Parses JSON output for cost, turns, and duration metrics.
"""

from __future__ import annotations

import asyncio
import json
import os

import structlog

from apps.runner.engines.subprocess_util import run_engine_subprocess, tail
from apps.runner.models import RunnerResult, RunnerTask
from apps.runner.sandbox import SandboxConfig, build_docker_cmd

logger = structlog.get_logger()

# Models that Claude Code natively supports.
SUPPORTED_MODELS = [
    "claude-opus-4-6",
    "claude-sonnet-4-6",
    "claude-haiku-4-5",
]

DEFAULT_MODEL = "claude-sonnet-4-6"


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


class ClaudeCodeAdapter:
    """Wraps the ``claude`` CLI for headless agent execution.

    Requires: ``claude`` binary on PATH (installed via
    ``npm i -g @anthropic-ai/claude-code``).

    Environment:
        ANTHROPIC_API_KEY:      Required. Anthropic API key (empty string for OpenRouter).
        ANTHROPIC_BASE_URL:     Optional. Override for OpenRouter, LiteLLM proxy, etc.
        ANTHROPIC_AUTH_TOKEN:   Optional. Bearer token for OpenRouter/proxy auth.
        CLAUDE_CODE_USE_BEDROCK: Optional. Set to "1" to use Amazon Bedrock.
        CLAUDE_CODE_USE_VERTEX:  Optional. Set to "1" to use Google Vertex AI.
    """

    @property
    def name(self) -> str:
        return "claude-code"

    @property
    def supported_models(self) -> list[str]:
        return SUPPORTED_MODELS

    async def run(
        self,
        task: RunnerTask,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> RunnerResult:
        """Execute task via ``claude --print --output-format json``.

        When ``task.sandbox_mode`` is True, the command is wrapped in a
        Docker container using ``build_docker_cmd`` for isolated execution.
        """
        model = task.model or DEFAULT_MODEL

        cmd: list[str] = [
            "claude",
            "--print",
            "--model", model,
            "--max-turns", str(task.max_turns),
            "--output-format", "json",
            "--verbose",
        ]

        env_overrides: dict[str, str] = {**task.env_vars}

        # Prevent "cannot launch inside another Claude Code session" error
        # when the runner itself is invoked from Claude Code.
        env_overrides["CLAUDECODE"] = ""

        api_key = _get_env("ANTHROPIC_API_KEY")
        if api_key:
            env_overrides["ANTHROPIC_API_KEY"] = api_key
        base_url = _get_env("ANTHROPIC_BASE_URL")
        if base_url:
            env_overrides["ANTHROPIC_BASE_URL"] = base_url
        auth_token = _get_env("ANTHROPIC_AUTH_TOKEN")
        if auth_token:
            env_overrides["ANTHROPIC_AUTH_TOKEN"] = auth_token

        for env_key in ("CLAUDE_CODE_USE_BEDROCK", "CLAUDE_CODE_USE_VERTEX"):
            value = _get_env(env_key)
            if value:
                env_overrides[env_key] = value

        workspace = task.workspace_path if hasattr(task, "workspace_path") else None
        if workspace is None:
            return RunnerResult(
                task_id=task.task_id,
                status="failure",
                engine=self.name,
                model=model,
                error_message="No workspace path set on task",
            )

        if task.sandbox_mode:
            sandbox_config = SandboxConfig(image=task.sandbox_image)
            cmd = build_docker_cmd(
                sandbox_config,
                cmd,
                workspace_path=str(workspace),
                env_vars=env_overrides,
            )
            logger.info(
                "engine.sandbox.enabled",
                engine=self.name,
                image=task.sandbox_image,
            )

        result = await run_engine_subprocess(
            cmd,
            cwd=workspace,
            env_overrides=env_overrides,
            timeout_seconds=task.timeout_seconds,
            stdin_text=task.description,
            cancel_event=cancel_event,
        )

        if result.cancelled:
            return RunnerResult(
                task_id=task.task_id,
                status="cancelled",
                engine=self.name,
                model=model,
                duration_ms=result.duration_ms,
                stdout_tail=tail(result.stdout),
                stderr_tail=tail(result.stderr),
            )

        if result.timed_out:
            return RunnerResult(
                task_id=task.task_id,
                status="timeout",
                engine=self.name,
                model=model,
                duration_ms=result.duration_ms,
                stdout_tail=tail(result.stdout),
                stderr_tail=tail(result.stderr),
            )

        # Parse JSON output for metrics
        cost_usd, num_turns = _parse_claude_output(result.stdout)

        succeeded = result.return_code == 0
        error_msg = None if succeeded else tail(result.stderr)

        return RunnerResult(
            task_id=task.task_id,
            status="success" if succeeded else "failure",
            engine=self.name,
            model=model,
            cost_usd=cost_usd,
            num_turns=num_turns,
            duration_ms=result.duration_ms,
            stdout_tail=tail(result.stdout),
            stderr_tail=tail(result.stderr),
            error_message=error_msg,
        )

    async def check_available(self) -> bool:
        """Check if ``claude`` CLI is on PATH."""
        from pathlib import Path

        result = await run_engine_subprocess(
            ["claude", "--version"],
            cwd=Path.cwd(),
            timeout_seconds=10,
        )
        return result.return_code == 0


def _parse_claude_output(stdout: str) -> tuple[float, int]:
    """Extract cost and turn count from Claude's JSON output.

    Claude --output-format json produces NDJSON. The last line
    contains the result object with cost_usd and num_turns.

    Returns:
        (cost_usd, num_turns) tuple. Defaults to (0.0, 0) on parse failure.
    """
    lines = stdout.strip().splitlines()
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if not isinstance(data, dict):
                continue
            cost = float(data.get("cost_usd", 0.0) or 0.0)
            turns = int(data.get("num_turns", 0) or 0)
            return cost, turns
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return 0.0, 0
