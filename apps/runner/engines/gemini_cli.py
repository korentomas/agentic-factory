"""
Gemini CLI engine adapter.

Wraps the ``gemini`` CLI for headless execution with Google models.

Requires: ``gemini`` binary on PATH (installed via
``npm i -g @google/gemini-cli``).

Environment:
    GEMINI_API_KEY:          Required. Google AI Studio API key.
    GOOGLE_GEMINI_BASE_URL:  Optional. Custom API endpoint for proxies.
    GOOGLE_CLOUD_PROJECT:    Optional. GCP project for Vertex AI mode.
    GOOGLE_CLOUD_LOCATION:   Optional. GCP region for Vertex AI mode.
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
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-pro-preview",
    "gemini-3-flash-preview",
]

DEFAULT_MODEL = "gemini-2.5-flash"


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


class GeminiCliAdapter:
    """Wraps the ``gemini`` CLI for headless agent execution.

    Requires: ``gemini`` binary on PATH (installed via
    ``npm i -g @google/gemini-cli``).

    Environment:
        GEMINI_API_KEY:          Required. Google AI Studio API key.
        GOOGLE_GEMINI_BASE_URL:  Optional. Custom API endpoint for proxies.
        GOOGLE_CLOUD_PROJECT:    Optional. GCP project for Vertex AI mode.
        GOOGLE_CLOUD_LOCATION:   Optional. GCP region for Vertex AI mode.
    """

    @property
    def name(self) -> str:
        """Engine identifier."""
        return "gemini-cli"

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
        """Execute task via ``gemini --model {model} {prompt}``.

        When ``task.sandbox_mode`` is True, the command is wrapped in a
        Docker container using ``build_docker_cmd`` for isolated execution.
        """
        model = task.model or DEFAULT_MODEL

        cmd: list[str] = [
            "gemini",
            "--model", model,
            task.description,
        ]

        env_overrides: dict[str, str] = {**task.env_vars}
        api_key = _get_env("GEMINI_API_KEY")
        if api_key:
            env_overrides["GEMINI_API_KEY"] = api_key
        base_url = _get_env("GOOGLE_GEMINI_BASE_URL")
        if base_url:
            env_overrides["GOOGLE_GEMINI_BASE_URL"] = base_url
        for env_key in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"):
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
            cost_usd=0.0,  # Gemini CLI doesn't report cost
            duration_ms=result.duration_ms,
            stdout_tail=tail(result.stdout),
            stderr_tail=tail(result.stderr),
            error_message=error_msg,
        )

    async def check_available(self) -> bool:
        """Check if ``gemini`` CLI is on PATH."""
        from pathlib import Path

        result = await run_engine_subprocess(
            ["gemini", "--version"],
            cwd=Path.cwd(),
            timeout_seconds=10,
        )
        return result.return_code == 0
