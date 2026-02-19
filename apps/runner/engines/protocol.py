"""
Engine protocol — the contract every engine adapter must implement.

Uses Python's Protocol (structural subtyping) so adapters don't need
to inherit from a base class. Just implement the interface.
"""

from __future__ import annotations

import asyncio
from typing import Protocol, runtime_checkable

from apps.runner.models import RunnerResult, RunnerTask


@runtime_checkable
class AgentEngine(Protocol):
    """Interface that every engine adapter must satisfy.

    Adapters wrap CLI tools (claude, aider, codex, kimi, etc.) as
    subprocesses and translate their output into RunnerResult.
    """

    @property
    def name(self) -> str:
        """Engine identifier (e.g. 'claude-code', 'aider', 'kimi-cli')."""
        ...

    @property
    def supported_models(self) -> list[str]:
        """Model identifiers this engine natively supports.

        Return ``["*"]`` for engines that support arbitrary models
        (e.g. aider via LiteLLM).
        """
        ...

    async def run(
        self,
        task: RunnerTask,
        *,
        cancel_event: asyncio.Event | None = None,
    ) -> RunnerResult:
        """Execute the task in the engine and return structured results.

        The engine should:
        1. Build the CLI command from task parameters
        2. Run it as a subprocess in task.workspace_path
        3. Parse stdout/stderr into RunnerResult fields
        4. Respect task.timeout_seconds
        5. Monitor cancel_event for early termination

        Args:
            task:         The task to execute.
            cancel_event: If provided, the engine should pass this to
                          run_engine_subprocess for graceful cancellation.

        Returns:
            RunnerResult with execution metadata.
        """
        ...

    async def check_available(self) -> bool:
        """Return True if the engine CLI binary is installed and accessible."""
        ...
