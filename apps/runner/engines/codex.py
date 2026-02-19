"""
Codex engine adapter.

Wraps the ``codex`` CLI for headless execution with OpenAI models.
"""

from __future__ import annotations

import asyncio
import os

import structlog

from apps.runner.engines.subprocess_util import run_engine_subprocess, tail
from apps.runner.models import RunnerResult, RunnerTask
from apps.runner.sandbox import SandboxConfig, build_docker_cmd

logger = structlog.get_logger()

SUPPORTED_MODELS = [
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4.1-nano",
    "o3",
    "o3-mini",
    "o1",
    "o1-mini",
]

DEFAULT_MODEL = "gpt-4.1"


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


class CodexAdapter:
    """Wraps the ``codex`` CLI for headless agent execution.

    Requires: ``codex`` binary on PATH (installed via
    ``npm i -g @openai/codex``).

    Environment:
        OPENAI_API_KEY: Required. OpenAI API key.
    """

    @property
    def name(self) -> str:
        """Engine identifier."""
        return "codex"

    @property
    def supported_models(self) -> list[str]:
        """Model identifiers this engine natively supports."""
        return SUPPORTED_MODELS

    async def run(
        self,
        task: RunnerTask,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> RunnerResult:
        """Execute task via ``codex --quiet --model {model}``.

        When ``task.sandbox_mode`` is True, the command is wrapped in a
        Docker container using ``build_docker_cmd`` for isolated execution.
        """
        model = task.model or DEFAULT_MODEL

        cmd: list[str] = [
            "codex",
            "--quiet",
            "--model", model,
            "--message", task.description,
        ]

        env_overrides: dict[str, str] = {**task.env_vars}
        api_key = _get_env("OPENAI_API_KEY")
        if api_key:
            env_overrides["OPENAI_API_KEY"] = api_key

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

        succeeded = result.return_code == 0
        error_msg = None if succeeded else tail(result.stderr)

        return RunnerResult(
            task_id=task.task_id,
            status="success" if succeeded else "failure",
            engine=self.name,
            model=model,
            cost_usd=0.0,  # Codex CLI doesn't report cost
            duration_ms=result.duration_ms,
            stdout_tail=tail(result.stdout),
            stderr_tail=tail(result.stderr),
            error_message=error_msg,
        )

    async def check_available(self) -> bool:
        """Check if ``codex`` CLI is on PATH."""
        from pathlib import Path

        result = await run_engine_subprocess(
            ["codex", "--version"],
            cwd=Path.cwd(),
            timeout_seconds=10,
        )
        return result.return_code == 0
