"""
Claude Code engine adapter.

Wraps the ``claude`` CLI in ``--print`` mode for headless execution.
Parses JSON output for cost, turns, and duration metrics.
"""

from __future__ import annotations

import json
import os

import structlog

from apps.runner.engines.subprocess_util import run_engine_subprocess, tail
from apps.runner.models import RunnerResult, RunnerTask

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
        ANTHROPIC_API_KEY:  Required. Anthropic API key.
        ANTHROPIC_BASE_URL: Optional. Override for OpenRouter, etc.
    """

    @property
    def name(self) -> str:
        return "claude-code"

    @property
    def supported_models(self) -> list[str]:
        return SUPPORTED_MODELS

    async def run(self, task: RunnerTask) -> RunnerResult:
        """Execute task via ``claude --print --output-format json``."""
        model = task.model or DEFAULT_MODEL

        cmd = [
            "claude",
            "--print",
            "--model", model,
            "--max-turns", str(task.max_turns),
            "--output-format", "json",
            "--verbose",
        ]

        env_overrides: dict[str, str] = {**task.env_vars}
        api_key = _get_env("ANTHROPIC_API_KEY")
        if api_key:
            env_overrides["ANTHROPIC_API_KEY"] = api_key
        base_url = _get_env("ANTHROPIC_BASE_URL")
        if base_url:
            env_overrides["ANTHROPIC_BASE_URL"] = base_url

        workspace = task.workspace_path if hasattr(task, "workspace_path") else None
        if workspace is None:
            return RunnerResult(
                task_id=task.task_id,
                status="failure",
                engine=self.name,
                model=model,
                error_message="No workspace path set on task",
            )

        result = await run_engine_subprocess(
            cmd,
            cwd=workspace,
            env_overrides=env_overrides,
            timeout_seconds=task.timeout_seconds,
            stdin_text=task.description,
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

        status = "success" if result.return_code == 0 else "failure"
        error_msg = None if status == "success" else tail(result.stderr)

        return RunnerResult(
            task_id=task.task_id,
            status=status,
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
            cost = float(data.get("cost_usd", 0.0) or 0.0)
            turns = int(data.get("num_turns", 0) or 0)
            return cost, turns
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    return 0.0, 0
