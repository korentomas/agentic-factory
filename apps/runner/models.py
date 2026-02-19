"""
Domain models for the Agent Runner.

AgentTask represents work to be done; AgentResult represents the outcome.
Both are frozen dataclasses — immutable after construction.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Literal


class TaskStatus(StrEnum):
    """Lifecycle states of an agent task."""

    PENDING = "pending"
    RUNNING = "running"
    COMMITTING = "committing"
    COMPLETE = "complete"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass(frozen=True)
class RunnerTask:
    """A task to be executed by the Agent Runner.

    Frozen (immutable) — tasks are created once from the orchestrator
    request and never mutated during execution.

    Attributes:
        task_id:          Unique identifier (e.g. "gh-42", "cu-abc123").
        repo_url:         Git clone URL.
        branch:           Branch to create/use for agent work.
        base_branch:      Branch to diff against (usually "main").
        title:            Human-readable task title.
        description:      Full task description / prompt for the agent.
        risk_tier:        Risk classification from triage.
        complexity:       Complexity classification from triage.
        engine:           Engine override (None = auto-select from model).
        model:            Model to use (None = engine default).
        max_turns:        Maximum agent turns before stopping.
        timeout_seconds:  Hard timeout for the entire task.
        env_vars:         Additional env vars to inject into the engine process.
        constitution:     CLAUDE.md contents or path to inject.
        callback_url:     URL to POST result to when complete.
        max_cost_usd:     Cost ceiling (0.0 = unlimited).
        sandbox_mode:     Run engine in Docker sandbox.
        sandbox_image:    Docker image for sandbox execution.
    """

    task_id: str
    repo_url: str
    branch: str
    base_branch: str
    title: str = ""
    description: str = ""
    risk_tier: Literal["high", "medium", "low"] = "medium"
    complexity: Literal["high", "standard"] = "standard"
    engine: str | None = None
    model: str | None = None
    max_turns: int = 40
    timeout_seconds: int = 3600
    env_vars: dict[str, str] = field(default_factory=dict)
    constitution: str = ""
    callback_url: str | None = None
    max_cost_usd: float = 0.0
    sandbox_mode: bool = False
    sandbox_image: str = "lailatov/sandbox:python"

    def __post_init__(self) -> None:
        if not self.task_id:
            raise ValueError("task_id is required")
        if not self.repo_url:
            raise ValueError("repo_url is required")
        if not self.description:
            raise ValueError("description is required")


@dataclass(frozen=True)
class RunnerResult:
    """Structured output from an agent task execution.

    Attributes:
        task_id:        Matches the input task.
        status:         Terminal status of the task.
        engine:         Engine that actually ran.
        model:          Model that actually ran.
        files_changed:  List of file paths modified by the agent.
        cost_usd:       Total LLM API cost (0.0 if unavailable).
        num_turns:      Number of agent turns completed.
        duration_ms:    Wall-clock execution time.
        commit_sha:     Git commit SHA of the agent's work (None if no commit).
        error_message:  Error details if status is not "success".
        stdout_tail:    Last N chars of stdout for debugging.
        stderr_tail:    Last N chars of stderr for debugging.
    """

    task_id: str
    status: Literal["success", "failure", "timeout", "cancelled"]
    engine: str
    model: str
    files_changed: list[str] = field(default_factory=list)
    cost_usd: float = 0.0
    num_turns: int = 0
    duration_ms: int = 0
    commit_sha: str | None = None
    error_message: str | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


def generate_task_id() -> str:
    """Generate a unique task ID."""
    return f"run-{uuid.uuid4().hex[:12]}"


@dataclass
class TaskState:
    """Mutable runtime state for a task being executed.

    Unlike RunnerTask and RunnerResult (which are frozen), this tracks
    the evolving status during execution.

    Attributes:
        task:           The frozen task definition.
        status:         Current lifecycle status.
        result:         Terminal result (set when complete/failed).
        workspace_path: Local checkout path.
        cancel_event:   Signaled to request cancellation.
        _async_task:    Handle to the background asyncio task.
    """

    task: RunnerTask
    status: TaskStatus = TaskStatus.PENDING
    result: RunnerResult | None = None
    workspace_path: Path | None = None
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    _async_task: asyncio.Task[None] | None = field(default=None, repr=False)
