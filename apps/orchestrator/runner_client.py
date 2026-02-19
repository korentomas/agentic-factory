"""
HTTP client for dispatching tasks to the LailaTov Agent Runner service.

The RunnerClient is the bridge between the orchestrator (webhook handler)
and the Agent Runner (subprocess executor). It translates orchestrator
AgentTask objects into RunnerTask HTTP requests.

Usage::

    client = RunnerClient()
    result = await client.submit_task(agent_task)

Configuration:
    RUNNER_URL:      Base URL of the Agent Runner service (default: http://localhost:8001)
    RUNNER_API_KEY:  Optional API key for runner authentication
    GITHUB_REPO:     Used to derive repo_url for the runner
"""

from __future__ import annotations

import os

import httpx
import structlog

from apps.orchestrator.models import AgentTask
from apps.orchestrator.providers import (
    PipelineStage,
    get_engine_for_stage,
    get_model_for_stage,
)

logger = structlog.get_logger(__name__)


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


class RunnerClient:
    """HTTP client for the LailaTov Agent Runner service.

    Translates AgentTask (orchestrator domain) into RunnerTask
    HTTP requests (runner domain).
    """

    def __init__(self, base_url: str | None = None) -> None:
        self._base_url = base_url

    @property
    def base_url(self) -> str:
        """Resolve base URL at call time from env or constructor arg."""
        return self._base_url or _get_env("RUNNER_URL", "http://localhost:8001")

    async def submit_task(
        self,
        task: AgentTask,
        *,
        stage: PipelineStage = PipelineStage.WRITE,
        github_token: str | None = None,
    ) -> dict[str, str]:
        """Submit a task to the Agent Runner.

        Translates the orchestrator's AgentTask into the runner's
        expected HTTP request format and sends it.

        Args:
            task:          The parsed AgentTask from the orchestrator.
            stage:         Pipeline stage (determines engine and model selection).
            github_token:  GitHub token for the runner to clone/push.

        Returns:
            Response dict with task_id and status.

        Raises:
            RunnerError: If the runner rejects or is unreachable.
        """
        log = logger.bind(task_id=task.clickup_task_id, stage=stage.value)

        github_repo = _get_env("GITHUB_REPO")
        repo_url = f"https://github.com/{github_repo}" if github_repo else ""

        # Resolve engine and model for this stage
        engine = get_engine_for_stage(stage)
        model = get_model_for_stage(stage, risk_tier=task.risk_tier)

        payload = {
            "task_id": f"cu-{task.clickup_task_id}",
            "repo_url": repo_url,
            "branch": task.branch,
            "base_branch": "main",
            "title": task.title,
            "description": task.description,
            "risk_tier": task.risk_tier,
            "complexity": task.complexity,
            "engine": engine,
            "model": model,
            "github_token": github_token or _get_env("GITHUB_APP_TOKEN"),
        }

        log.info("runner.submit", engine=engine, model=model)

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                headers: dict[str, str] = {"Content-Type": "application/json"}
                api_key = _get_env("RUNNER_API_KEY")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                resp = await client.post(
                    f"{self.base_url}/tasks",
                    json=payload,
                    headers=headers,
                )
                resp.raise_for_status()
                result = resp.json()

        except httpx.HTTPStatusError as exc:
            log.error(
                "runner.submit.http_error",
                status_code=exc.response.status_code,
                body=exc.response.text[:500],
            )
            raise RunnerError(
                f"Runner rejected task (HTTP {exc.response.status_code})"
            ) from exc
        except httpx.RequestError as exc:
            log.error("runner.submit.connection_error", error=str(exc))
            raise RunnerError(f"Runner unreachable: {exc}") from exc

        log.info("runner.submit.accepted", runner_task_id=result.get("task_id"))
        return result

    async def get_task_status(self, task_id: str) -> dict[str, object]:
        """Poll the runner for task status.

        Args:
            task_id: The runner task ID (e.g. "cu-abc123").

        Returns:
            Status dict from the runner.

        Raises:
            RunnerError: If the runner is unreachable or returns an error.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                headers: dict[str, str] = {}
                api_key = _get_env("RUNNER_API_KEY")
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"

                resp = await client.get(
                    f"{self.base_url}/tasks/{task_id}",
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json()

        except httpx.HTTPStatusError as exc:
            raise RunnerError(
                f"Runner status check failed (HTTP {exc.response.status_code})"
            ) from exc
        except httpx.RequestError as exc:
            raise RunnerError(f"Runner unreachable: {exc}") from exc

    async def health_check(self) -> bool:
        """Check if the runner service is healthy.

        Returns:
            True if the runner responds with status "ok".
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except httpx.RequestError:
            return False


class RunnerError(Exception):
    """Raised when the Agent Runner returns an error or is unreachable."""
