"""
Workspace management for the Agent Runner.

Each task gets an isolated workspace directory with a shallow clone
of the target repo. Handles clone, branch creation, commit, and push.

Security: All git commands use asyncio.create_subprocess_exec which
passes arguments as a list (no shell interpolation, no injection risk).
"""

from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path

import structlog

logger = structlog.get_logger()


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


# Default workspace root. Overridable via LAILATOV_WORKSPACE_ROOT.
DEFAULT_WORKSPACE_ROOT = "/tmp/lailatov-workspaces"  # noqa: S108


async def _run_git(
    args: list[str],
    cwd: Path,
    env: dict[str, str] | None = None,
    timeout: int = 300,
) -> tuple[int, str, str]:
    """Run a git command safely via create_subprocess_exec (no shell).

    Returns (return_code, stdout, stderr).
    """
    full_env = {**os.environ, **(env or {})}
    proc = await asyncio.create_subprocess_exec(
        "git", *args,
        cwd=cwd,
        env=full_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except TimeoutError:
        proc.kill()
        await proc.wait()
        return -1, "", "git command timed out"

    return (
        proc.returncode or 0,
        stdout_b.decode("utf-8", errors="replace").strip(),
        stderr_b.decode("utf-8", errors="replace").strip(),
    )


def get_workspace_root() -> Path:
    """Return the workspace root directory."""
    root = _get_env("LAILATOV_WORKSPACE_ROOT", DEFAULT_WORKSPACE_ROOT)
    return Path(root)


async def create_workspace(
    task_id: str,
    repo_url: str,
    branch: str,
    base_branch: str = "main",
    github_token: str | None = None,
) -> Path:
    """Create an isolated workspace for a task.

    1. Creates workspace directory structure
    2. Shallow clones the repo
    3. Creates and checks out the working branch

    Args:
        task_id:      Unique task identifier (used as directory name).
        repo_url:     Git clone URL (https).
        branch:       Branch to create for agent work.
        base_branch:  Branch to base work on (usually "main").
        github_token: Optional token for authenticated clone.

    Returns:
        Path to the repo checkout within the workspace.

    Raises:
        RuntimeError: If clone or branch creation fails.
    """
    root = get_workspace_root()
    workspace = root / task_id
    repo_path = workspace / "repo"

    # Clean up any stale workspace
    if workspace.exists():
        shutil.rmtree(workspace)

    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "output").mkdir()
    (workspace / "logs").mkdir()

    # Inject token into clone URL if provided
    clone_url = repo_url
    if github_token and clone_url.startswith("https://"):
        clone_url = clone_url.replace(
            "https://", f"https://x-access-token:{github_token}@"
        )

    logger.info("workspace.clone", task_id=task_id, repo_url=repo_url)

    # Shallow clone
    code, stdout, stderr = await _run_git(
        ["clone", "--depth", "1", "--branch", base_branch, clone_url, "repo"],
        cwd=workspace,
        timeout=120,
    )
    if code != 0:
        raise RuntimeError(f"git clone failed (code {code}): {stderr}")

    # Create working branch
    code, stdout, stderr = await _run_git(
        ["checkout", "-b", branch],
        cwd=repo_path,
    )
    if code != 0:
        raise RuntimeError(f"git checkout -b {branch} failed: {stderr}")

    # Configure git user for commits
    await _run_git(["config", "user.name", "LailaTov Agent"], cwd=repo_path)
    await _run_git(["config", "user.email", "agent@lailatov.dev"], cwd=repo_path)

    logger.info("workspace.ready", task_id=task_id, path=str(repo_path))
    return repo_path


async def commit_changes(
    repo_path: Path,
    message: str,
) -> str | None:
    """Stage all changes and commit.

    Args:
        repo_path: Path to the git repo.
        message:   Commit message.

    Returns:
        Commit SHA string, or None if nothing to commit.
    """
    # Stage everything
    await _run_git(["add", "-A"], cwd=repo_path)

    # Check if there's anything to commit
    code, stdout, _ = await _run_git(["diff", "--cached", "--quiet"], cwd=repo_path)
    if code == 0:
        logger.info("workspace.commit.nothing")
        return None

    # Commit
    code, stdout, stderr = await _run_git(
        ["commit", "-m", message],
        cwd=repo_path,
    )
    if code != 0:
        logger.error("workspace.commit.failed", stderr=stderr)
        return None

    # Get SHA
    code, sha, _ = await _run_git(["rev-parse", "HEAD"], cwd=repo_path)
    logger.info("workspace.commit.done", sha=sha[:12])
    return sha


async def push_changes(
    repo_path: Path,
    branch: str,
) -> bool:
    """Push the working branch to origin.

    Args:
        repo_path: Path to the git repo.
        branch:    Branch name to push.

    Returns:
        True if push succeeded.
    """
    code, stdout, stderr = await _run_git(
        ["push", "-u", "origin", branch],
        cwd=repo_path,
        timeout=60,
    )
    if code != 0:
        logger.error("workspace.push.failed", stderr=stderr)
        return False

    logger.info("workspace.push.done", branch=branch)
    return True


async def cleanup_workspace(task_id: str) -> None:
    """Remove a task's workspace directory."""
    root = get_workspace_root()
    workspace = root / task_id
    if workspace.exists():
        shutil.rmtree(workspace)
        logger.info("workspace.cleanup", task_id=task_id)


async def list_changed_files(repo_path: Path, base_branch: str = "main") -> list[str]:
    """List files changed relative to the base branch.

    Falls back to listing uncommitted changes if base branch
    comparison fails (common with shallow clones).
    """
    # Try diff against base
    code, stdout, _ = await _run_git(
        ["diff", "--name-only", f"origin/{base_branch}...HEAD"],
        cwd=repo_path,
    )
    if code == 0 and stdout:
        return [f for f in stdout.splitlines() if f.strip()]

    # Fallback: list all modified/added files
    code, stdout, _ = await _run_git(
        ["diff", "--name-only", "HEAD~1"],
        cwd=repo_path,
    )
    if code == 0 and stdout:
        return [f for f in stdout.splitlines() if f.strip()]

    return []
