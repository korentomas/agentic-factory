"""
Shared subprocess utilities for engine adapters.

Handles async subprocess execution with timeout, output capture,
cancellation support, and structured error reporting.

Security note: Uses asyncio.create_subprocess_exec (not shell=True).
Arguments are passed as a list, preventing shell injection.
"""

from __future__ import annotations

import asyncio
import os
import time
from dataclasses import dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger()

# Maximum chars to keep from stdout/stderr tails.
OUTPUT_TAIL_LIMIT = 5000

# Grace period before escalating SIGTERM to SIGKILL.
_SIGTERM_GRACE_SECONDS = 5


@dataclass(frozen=True)
class SubprocessResult:
    """Raw output from a subprocess execution."""

    return_code: int
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    cancelled: bool = False


async def _wait_for_event(event: asyncio.Event) -> None:
    """Wait until an event is set."""
    await event.wait()


async def run_engine_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    env_overrides: dict[str, str] | None = None,
    timeout_seconds: int = 3600,
    stdin_text: str | None = None,
    cancel_event: asyncio.Event | None = None,
) -> SubprocessResult:
    """Run an engine CLI command as an async subprocess.

    Uses create_subprocess_exec (not shell) to prevent injection.

    Args:
        cmd:             Command and arguments to execute.
        cwd:             Working directory for the subprocess.
        env_overrides:   Additional env vars to set (merged with current env).
        timeout_seconds: Hard timeout. Process is killed after this.
        stdin_text:      Optional text to pipe to stdin.
        cancel_event:    If set, monitor this event for cancellation.
                         SIGTERM is sent first, then SIGKILL after grace period.

    Returns:
        SubprocessResult with captured output and timing.
    """
    env = {**os.environ, **(env_overrides or {})}

    logger.info(
        "engine.subprocess.start",
        cmd=cmd[:3],  # Log first 3 elements to avoid leaking prompts
        cwd=str(cwd),
        timeout=timeout_seconds,
    )

    start_ms = _now_ms()
    timed_out = False
    cancelled = False

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE if stdin_text else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        if cancel_event is not None:
            # Race between process completion, timeout, and cancellation
            process_task = asyncio.create_task(
                proc.communicate(input=stdin_text.encode() if stdin_text else None)
            )
            cancel_task = asyncio.create_task(_wait_for_event(cancel_event))

            done, pending = await asyncio.wait(
                {process_task, cancel_task},
                timeout=timeout_seconds,
                return_when=asyncio.FIRST_COMPLETED,
            )

            for t in pending:
                t.cancel()
                try:
                    await t
                except asyncio.CancelledError:
                    pass

            if cancel_task in done:
                # Cancellation requested: SIGTERM then SIGKILL
                cancelled = True
                logger.info("engine.subprocess.cancelling", pid=proc.pid)
                proc.terminate()
                try:
                    await asyncio.wait_for(proc.wait(), timeout=_SIGTERM_GRACE_SECONDS)
                except TimeoutError:
                    proc.kill()
                    await proc.wait()
                stdout_bytes = b""
                stderr_bytes = b"Process cancelled"
            elif process_task in done:
                # Process completed normally
                stdout_bytes, stderr_bytes = process_task.result()
            else:
                # Timeout (neither done)
                timed_out = True
                proc.kill()
                await proc.wait()
                stdout_bytes = b""
                stderr_bytes = b"Process killed: timeout exceeded"
        else:
            # Original path (no cancellation support)
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    proc.communicate(input=stdin_text.encode() if stdin_text else None),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                timed_out = True
                proc.kill()
                await proc.wait()
                stdout_bytes = b""
                stderr_bytes = b"Process killed: timeout exceeded"

    except FileNotFoundError:
        duration_ms = _now_ms() - start_ms
        return SubprocessResult(
            return_code=-1,
            stdout="",
            stderr=f"Command not found: {cmd[0]}",
            duration_ms=duration_ms,
            timed_out=False,
        )

    duration_ms = _now_ms() - start_ms
    stdout = stdout_bytes.decode("utf-8", errors="replace")
    stderr = stderr_bytes.decode("utf-8", errors="replace")

    logger.info(
        "engine.subprocess.done",
        return_code=proc.returncode,
        duration_ms=duration_ms,
        timed_out=timed_out,
        cancelled=cancelled,
        stdout_len=len(stdout),
        stderr_len=len(stderr),
    )

    return SubprocessResult(
        return_code=proc.returncode or 0,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        cancelled=cancelled,
    )


def tail(text: str, limit: int = OUTPUT_TAIL_LIMIT) -> str:
    """Return the last ``limit`` chars of text."""
    if len(text) <= limit:
        return text
    return f"...truncated...\n{text[-limit:]}"


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
