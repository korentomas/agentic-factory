"""
Oh-my-pi engine adapter.

Wraps the ``omp`` CLI (oh-my-pi) for headless execution.
Like aider, oh-my-pi supports multiple LLM providers via its
built-in model registry, making it a universal fallback engine.
"""

from __future__ import annotations

import asyncio
import os

import structlog

from apps.runner.engines.subprocess_util import run_engine_subprocess, tail
from apps.runner.models import RunnerResult, RunnerTask
from apps.runner.sandbox import SandboxConfig, build_docker_cmd

logger = structlog.get_logger()

# oh-my-pi is multi-provider — supports any model its registry knows.
SUPPORTED_MODELS: list[str] = ["*"]

DEFAULT_MODEL = "claude-sonnet-4-6"

_PROVIDER_ENV_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "GEMINI_API_KEY",
    "OPENROUTER_API_KEY",
    "GROQ_API_KEY",
    "MISTRAL_API_KEY",
)


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


class PiAdapter:
    """Wraps the ``omp`` CLI (oh-my-pi) for headless agent execution.

    oh-my-pi is a multi-provider coding agent with hash-anchored edits,
    LSP integration, and subagent support. Like aider, it can route to
    virtually any LLM provider.

    Requires: ``omp`` binary on PATH (installed via
    ``bun install -g @oh-my-pi/pi-coding-agent``).

    Environment:
        ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, etc.
        — whichever provider the chosen model requires.
    """

    @property
    def name(self) -> str:
        """Engine identifier."""
        return "oh-my-pi"

    @property
    def supported_models(self) -> list[str]:
        """oh-my-pi supports any model its registry knows."""
        return SUPPORTED_MODELS

    async def run(
        self,
        task: RunnerTask,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> RunnerResult:
        """Execute task via ``omp --no-session``.

        When ``task.sandbox_mode`` is True, the command is wrapped in a
        Docker container using ``build_docker_cmd`` for isolated execution.
        """
        model = task.model or DEFAULT_MODEL

        cmd: list[str] = [
            "omp",
            "--no-session",
            "--print",
            "--model", model,
            task.description,
        ]

        env_overrides: dict[str, str] = {**task.env_vars}

        # Inject API keys for all known providers
        for env_key in _PROVIDER_ENV_KEYS:
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
            cost_usd=0.0,  # omp doesn't report cost in CLI output
            duration_ms=result.duration_ms,
            stdout_tail=tail(result.stdout),
            stderr_tail=tail(result.stderr),
            error_message=error_msg,
        )

    async def check_available(self) -> bool:
        """Check if ``omp`` CLI is on PATH."""
        from pathlib import Path

        result = await run_engine_subprocess(
            ["omp", "--version"],
            cwd=Path.cwd(),
            timeout_seconds=10,
        )
        return result.return_code == 0
