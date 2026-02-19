"""
Aider engine adapter — the universal fallback.

Wraps the ``aider`` CLI which uses LiteLLM under the hood,
meaning it can route to virtually any LLM provider.
"""

from __future__ import annotations

import asyncio
import os
import re

import structlog

from apps.orchestrator.providers import PROVIDERS, derive_provider_from_model, get_provider_config
from apps.runner.engines.subprocess_util import run_engine_subprocess, tail
from apps.runner.models import RunnerResult, RunnerTask
from apps.runner.sandbox import SandboxConfig, build_docker_cmd

logger = structlog.get_logger()


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


def _resolve_provider_for_model(model: str) -> str:
    """Resolve the provider name for a model, handling LiteLLM prefixes.

    LiteLLM uses ``provider/model`` format (e.g. ``deepseek/deepseek-chat``),
    which differs from the orchestrator convention where ``/`` means OpenRouter.
    This function checks whether the prefix before the first ``/`` is a known
    provider and uses it directly; otherwise falls back to
    ``derive_provider_from_model``.

    Args:
        model: Model name, possibly with LiteLLM ``provider/`` prefix.

    Returns:
        Provider name string (e.g. ``"deepseek"``, ``"openrouter"``).
    """
    if "/" in model:
        prefix = model.split("/", 1)[0].lower()
        if prefix in PROVIDERS:
            return prefix
    return derive_provider_from_model(model)


class AiderAdapter:
    """Wraps the ``aider`` CLI for universal model support.

    Aider uses LiteLLM internally, so it can call Claude, GPT,
    Gemini, DeepSeek, Qwen, Kimi, and any OpenRouter model.

    Requires: ``aider`` binary on PATH (installed via
    ``pip install aider-chat``).
    """

    @property
    def name(self) -> str:
        return "aider"

    @property
    def supported_models(self) -> list[str]:
        return ["*"]  # Any LiteLLM-supported model

    async def run(
        self,
        task: RunnerTask,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> RunnerResult:
        """Execute task via ``aider --yes-always --message``.

        When ``task.sandbox_mode`` is True, the command is wrapped in a
        Docker container using ``build_docker_cmd`` for isolated execution.
        """
        model = task.model or "claude-sonnet-4-6"

        cmd: list[str] = [
            "aider",
            "--yes-always",
            "--no-auto-commits",
            "--no-git",
            "--no-stream",
            "--model", model,
            "--message", task.description,
        ]

        env_overrides: dict[str, str] = {**task.env_vars}

        # Inject the right API key from provider config
        provider_name = _resolve_provider_for_model(model)
        provider_config = get_provider_config(provider_name)
        if provider_config.api_key_env:
            key_value = _get_env(provider_config.api_key_env)
            if key_value:
                env_overrides[provider_config.api_key_env] = key_value

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

        # Aider doesn't output structured cost data, but we can try to parse it
        cost_usd = _parse_aider_cost(result.stdout)
        succeeded = result.return_code == 0
        error_msg = None if succeeded else tail(result.stderr)

        return RunnerResult(
            task_id=task.task_id,
            status="success" if succeeded else "failure",
            engine=self.name,
            model=model,
            cost_usd=cost_usd,
            duration_ms=result.duration_ms,
            stdout_tail=tail(result.stdout),
            stderr_tail=tail(result.stderr),
            error_message=error_msg,
        )

    async def check_available(self) -> bool:
        """Check if ``aider`` CLI is on PATH."""
        from pathlib import Path

        result = await run_engine_subprocess(
            ["aider", "--version"],
            cwd=Path.cwd(),
            timeout_seconds=10,
        )
        return result.return_code == 0


def _parse_aider_cost(stdout: str) -> float:
    """Try to extract cost from aider's output.

    Aider sometimes prints cost summaries like:
    "Tokens: 12.3k sent, 4.5k received. Cost: $0.05"

    Returns:
        Extracted cost in USD, or 0.0 if not found.
    """
    match = re.search(r"Cost:\s*\$([0-9]+\.?[0-9]*)", stdout)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0
