"""
LailaTov Agent Runner — HTTP service for executing coding agents.

Receives task requests from the orchestrator, runs coding agents
as subprocesses, and returns structured results.

Usage::

    uvicorn apps.runner.main:app --host 0.0.0.0 --port 8001

Or::

    python -m apps.runner.main
"""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Literal, cast

import structlog
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from apps.runner.audit import AuditLog
from apps.runner.budget import BudgetExceededError, BudgetTracker
from apps.runner.circuit_breaker import CircuitBreaker, CircuitOpenError
from apps.runner.engines.registry import select_engine
from apps.runner.middleware import APIKeyMiddleware
from apps.runner.models import RunnerResult, RunnerTask, TaskState, TaskStatus
from apps.runner.watchdog import TaskWatchdog
from apps.runner.workspace import (
    cleanup_workspace,
    commit_changes,
    create_workspace,
    list_changed_files,
    push_changes,
)

logger = structlog.get_logger()


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


# ── In-memory task store ─────────────────────────────────────────────────────
# For v1, tasks are stored in memory. Future: Redis or database.
_tasks: dict[str, TaskState] = {}

# ── Audit log ────────────────────────────────────────────────────────────────
audit_log = AuditLog()

# ── Circuit breakers (per-engine) ────────────────────────────────────────────
_breakers: dict[str, CircuitBreaker] = {}


def get_breaker(engine_name: str) -> CircuitBreaker:
    """Get or create a circuit breaker for an engine."""
    if engine_name not in _breakers:
        _breakers[engine_name] = CircuitBreaker(name=engine_name)
    return _breakers[engine_name]


def reset_breakers() -> None:
    """Reset all circuit breakers. Used in tests."""
    _breakers.clear()


# ── Task watchdog ────────────────────────────────────────────────────────────
_watchdog: TaskWatchdog | None = None


# ── Pydantic request/response models ────────────────────────────────────────


class TaskRequest(BaseModel):
    """HTTP request body for submitting a task."""

    task_id: str
    repo_url: str
    branch: str
    base_branch: str = "main"
    title: str = ""
    description: str
    risk_tier: str = "medium"
    complexity: str = "standard"
    engine: str | None = None
    model: str | None = None
    max_turns: int = 40
    timeout_seconds: int = 3600
    env_vars: dict[str, str] = Field(default_factory=dict)
    constitution: str = ""
    callback_url: str | None = None
    github_token: str | None = None
    max_cost_usd: float = 0.0
    sandbox_mode: bool = False
    sandbox_image: str = "lailatov/sandbox:python"


class TaskResponse(BaseModel):
    """HTTP response for task status."""

    task_id: str
    status: str
    engine: str | None = None
    model: str | None = None
    files_changed: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    num_turns: int = 0
    duration_ms: int = 0
    commit_sha: str | None = None
    error_message: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    active_tasks: int
    version: str = "0.1.0"


# ── Lifespan ─────────────────────────────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    global _watchdog  # noqa: PLW0603
    logger.info("runner.startup", version="0.1.0")

    # Start the task watchdog
    _watchdog = TaskWatchdog(tasks=_tasks, audit_log=audit_log)
    await _watchdog.start()

    yield

    # Stop the watchdog
    if _watchdog is not None:
        await _watchdog.stop()
        _watchdog = None

    # Cleanup: cancel any running tasks
    for task_id, state in _tasks.items():
        if state.status == TaskStatus.RUNNING:
            logger.warning("runner.shutdown.orphan", task_id=task_id)
            state.cancel_event.set()
            if state._async_task and not state._async_task.done():
                state._async_task.cancel()
    _tasks.clear()
    audit_log.clear()
    reset_breakers()
    logger.info("runner.shutdown")


# ── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LailaTov Agent Runner",
    description="Executes coding agents as subprocesses",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(APIKeyMiddleware)


# ── Endpoints ────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Health check."""
    active = sum(
        1 for s in _tasks.values()
        if s.status in (TaskStatus.RUNNING, TaskStatus.COMMITTING)
    )
    return HealthResponse(status="ok", active_tasks=active)


@app.post("/tasks", response_model=TaskResponse, status_code=202)
async def submit_task(request: TaskRequest) -> TaskResponse:
    """Submit a new agent task for execution.

    Returns 202 Accepted immediately. The task runs in the background.
    Poll GET /tasks/{task_id} for status.
    """
    if request.task_id in _tasks:
        raise HTTPException(
            status_code=409,
            detail=f"Task {request.task_id} already exists",
        )

    # Validate risk_tier and complexity at the boundary
    risk_tier = cast(
        Literal["high", "medium", "low"],
        request.risk_tier if request.risk_tier in ("high", "medium", "low") else "medium",
    )
    complexity = cast(
        Literal["high", "standard"],
        request.complexity if request.complexity in ("high", "standard") else "standard",
    )

    runner_task = RunnerTask(
        task_id=request.task_id,
        repo_url=request.repo_url,
        branch=request.branch,
        base_branch=request.base_branch,
        title=request.title,
        description=request.description,
        risk_tier=risk_tier,
        complexity=complexity,
        engine=request.engine,
        model=request.model,
        max_turns=request.max_turns,
        timeout_seconds=request.timeout_seconds,
        env_vars=request.env_vars,
        constitution=request.constitution,
        callback_url=request.callback_url,
        max_cost_usd=request.max_cost_usd,
        sandbox_mode=request.sandbox_mode,
        sandbox_image=request.sandbox_image,
    )

    state = TaskState(task=runner_task)
    _tasks[request.task_id] = state

    audit_log.record("task.submitted", task_id=request.task_id, engine=request.engine)

    # Fire and forget — run in background, store handle for cancellation
    bg_task = asyncio.create_task(_execute_task(state, request.github_token))
    state._async_task = bg_task

    return TaskResponse(
        task_id=request.task_id,
        status=TaskStatus.PENDING,
    )


@app.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(task_id: str) -> TaskResponse:
    """Get the current status of a task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    state = _tasks[task_id]
    if state.result:
        return TaskResponse(
            task_id=task_id,
            status=state.status.value,
            engine=state.result.engine,
            model=state.result.model,
            files_changed=state.result.files_changed,
            cost_usd=state.result.cost_usd,
            num_turns=state.result.num_turns,
            duration_ms=state.result.duration_ms,
            commit_sha=state.result.commit_sha,
            error_message=state.result.error_message,
        )
    return TaskResponse(task_id=task_id, status=state.status.value)


@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str) -> dict[str, str]:
    """Cancel a running task."""
    if task_id not in _tasks:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    state = _tasks[task_id]
    if state.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
        raise HTTPException(
            status_code=400,
            detail=f"Task {task_id} is {state.status.value}, cannot cancel",
        )

    # Signal cancellation via event and cancel the async task
    state.cancel_event.set()
    if state._async_task and not state._async_task.done():
        state._async_task.cancel()

    state.status = TaskStatus.CANCELLED
    audit_log.record("task.cancelled", task_id=task_id)
    return {"task_id": task_id, "status": "cancelled"}


# ── GitHub App token rotation ────────────────────────────────────────────────

_token_manager = None  # Lazily initialized


async def _get_github_app_token(log: structlog.stdlib.BoundLogger) -> str | None:
    """Try to get a short-lived token via GitHub App, if configured.

    Returns None if the GitHub App is not configured (no env vars set).
    """
    global _token_manager  # noqa: PLW0603

    app_id = _get_env("GITHUB_APP_ID")
    installation_id = _get_env("GITHUB_APP_INSTALLATION_ID")
    private_key = _get_env("GITHUB_APP_PRIVATE_KEY")

    if not (app_id and installation_id and private_key):
        return None

    try:
        if _token_manager is None:
            from apps.runner.github_tokens import GitHubTokenManager

            _token_manager = GitHubTokenManager(
                app_id=int(app_id),
                private_key=private_key,
                installation_id=int(installation_id),
            )

        token = await _token_manager.get_token()
        log.info("task.github_app_token.acquired")
        return token
    except Exception as exc:
        log.warning("task.github_app_token.failed", error=str(exc))
        return None


# ── Task execution ───────────────────────────────────────────────────────────


async def _execute_task(state: TaskState, github_token: str | None = None) -> None:
    """Execute a task end-to-end: workspace → engine → commit → push.

    Integrates circuit breaker, budget enforcement, cancel_event,
    and audit trail at each lifecycle stage.
    """
    task = state.task
    log = logger.bind(task_id=task.task_id)
    budget = BudgetTracker(max_cost_usd=task.max_cost_usd)

    try:
        # 1. Create workspace
        state.status = TaskStatus.RUNNING
        state.started_at = time.monotonic()
        audit_log.record("task.started", task_id=task.task_id)
        log.info("task.workspace.creating")

        # Use GitHub App token rotation if no static token provided
        effective_token = github_token
        if not effective_token:
            effective_token = await _get_github_app_token(log)

        repo_path = await create_workspace(
            task_id=task.task_id,
            repo_url=task.repo_url,
            branch=task.branch,
            base_branch=task.base_branch,
            github_token=effective_token,
        )
        state.workspace_path = repo_path

        # 2. Select engine and check circuit breaker
        engine = select_engine(
            model=task.model,
            preferred_engine=task.engine,
        )
        breaker = get_breaker(engine.name)

        if not breaker.allow_request():
            raise CircuitOpenError(engine.name, breaker.recovery_timeout)

        audit_log.record(
            "task.engine_selected",
            task_id=task.task_id,
            engine=engine.name,
        )
        log.info("task.engine.selected", engine=engine.name)

        # Inject workspace path into task for the engine
        # (RunnerTask is frozen, so we use object.__setattr__)
        object.__setattr__(task, "workspace_path", repo_path)

        # 3. Run engine with cancel_event
        result = await engine.run(task, cancel_event=state.cancel_event)

        # 4. Record cost and check budget
        if result.cost_usd > 0:
            budget.record_cost(result.cost_usd)
            budget.check()

        # 5. Update circuit breaker
        if result.status == "success":
            breaker.record_success()
        elif result.status == "failure":
            breaker.record_failure()

        # 6. Commit and push if successful
        if result.status == "success":
            state.status = TaskStatus.COMMITTING
            log.info("task.committing")

            commit_msg = (
                f"feat: {task.title or 'agent task'}\n\n"
                f"Task: {task.task_id}\n"
                f"Engine: {engine.name}\n"
                f"Model: {result.model}\n\n"
                f"Co-Authored-By: LailaTov Agent <agent@lailatov.dev>"
            )
            sha = await commit_changes(repo_path, commit_msg)
            files = await list_changed_files(repo_path, task.base_branch)

            pushed = False
            if sha:
                pushed = await push_changes(repo_path, task.branch)

            result = RunnerResult(
                task_id=result.task_id,
                status=result.status,
                engine=result.engine,
                model=result.model,
                files_changed=files,
                cost_usd=result.cost_usd,
                num_turns=result.num_turns,
                duration_ms=result.duration_ms,
                commit_sha=sha,
                stdout_tail=result.stdout_tail,
                stderr_tail=result.stderr_tail,
            )

            if not pushed and sha:
                log.warning("task.push.failed")

        state.result = result
        state.status = (
            TaskStatus.COMPLETE if result.status == "success"
            else TaskStatus.FAILED
        )
        audit_log.record(
            "task.completed",
            task_id=task.task_id,
            status=state.status.value,
            cost_usd=result.cost_usd,
        )
        log.info("task.done", status=state.status.value)

    except asyncio.CancelledError:
        log.warning("task.cancelled")
        state.status = TaskStatus.CANCELLED
        state.result = RunnerResult(
            task_id=task.task_id,
            status="cancelled",
            engine=task.engine or "unknown",
            model=task.model or "unknown",
            error_message="Task was cancelled",
        )
        audit_log.record("task.cancelled", task_id=task.task_id)

    except CircuitOpenError as exc:
        log.warning("task.circuit_open", engine=exc.engine, retry_after=exc.retry_after)
        state.status = TaskStatus.FAILED
        state.result = RunnerResult(
            task_id=task.task_id,
            status="failure",
            engine=exc.engine,
            model=task.model or "unknown",
            error_message=str(exc),
        )
        audit_log.record(
            "task.circuit_open",
            task_id=task.task_id,
            engine=exc.engine,
        )

    except BudgetExceededError as exc:
        log.warning("task.budget_exceeded", spent=exc.spent, limit=exc.limit)
        state.status = TaskStatus.FAILED
        state.result = RunnerResult(
            task_id=task.task_id,
            status="failure",
            engine=task.engine or "unknown",
            model=task.model or "unknown",
            error_message=str(exc),
        )
        audit_log.record(
            "task.budget_exceeded",
            task_id=task.task_id,
            spent=exc.spent,
            limit=exc.limit,
        )

    except Exception as exc:
        log.error("task.failed", error=str(exc))
        state.status = TaskStatus.FAILED
        state.result = RunnerResult(
            task_id=task.task_id,
            status="failure",
            engine=task.engine or "unknown",
            model=task.model or "unknown",
            error_message=str(exc),
        )
        audit_log.record(
            "task.failed",
            task_id=task.task_id,
            error=str(exc),
        )

    finally:
        # Cleanup workspace (unless LAILATOV_KEEP_WORKSPACES is set)
        if not _get_env("LAILATOV_KEEP_WORKSPACES"):
            await cleanup_workspace(task.task_id)


# ── CLI entry point ──────────────────────────────────────────────────────────


def cli_main() -> None:
    """CLI entry point for running the Agent Runner."""
    import uvicorn

    host = _get_env("RUNNER_HOST", "0.0.0.0")  # noqa: S104
    port = int(_get_env("RUNNER_PORT", "8001"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    cli_main()
