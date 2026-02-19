"""
Shared fixtures and helpers for E2E engine tests.

These tests hit real APIs with real CLI binaries.
They are skipped gracefully when a CLI or API key is unavailable.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from apps.runner.engines.aider import AiderAdapter
from apps.runner.engines.claude_code import ClaudeCodeAdapter
from apps.runner.engines.codex import CodexAdapter
from apps.runner.engines.gemini_cli import GeminiCliAdapter
from apps.runner.engines.pi import PiAdapter

# Map engine name → CLI binary name used by shutil.which()
ENGINE_BINARIES: dict[str, str] = {
    "claude-code": "claude",
    "codex": "codex",
    "gemini-cli": "gemini",
    "aider": "aider",
    "oh-my-pi": "omp",
}

# Map engine name → adapter class
ENGINE_ADAPTERS: dict[str, type] = {
    "claude-code": ClaudeCodeAdapter,
    "codex": CodexAdapter,
    "gemini-cli": GeminiCliAdapter,
    "aider": AiderAdapter,
    "oh-my-pi": PiAdapter,
}

# Map engine name → required env var for its default provider
ENGINE_REQUIRED_ENV: dict[str, str] = {
    "claude-code": "ANTHROPIC_API_KEY",
    "codex": "OPENAI_API_KEY",
    "gemini-cli": "GEMINI_API_KEY",
    "aider": "ANTHROPIC_API_KEY",
    "oh-my-pi": "OPENAI_API_KEY",
}

# The buggy Python file used as the test workspace
_BUGGY_FILE = (
    'def add(a: int, b: int) -> int:\n'
    '    """Add two numbers."""\n'
    '    return a - b  # BUG: should be a + b\n'
)

# The prompt given to every engine
E2E_PROMPT = (
    "Fix the bug in math_utils.py — the add() function should return a + b, not a - b. "
    "Only change the return statement."
)


def has_binary(name: str) -> bool:
    """Check if a CLI binary is available on PATH."""
    return shutil.which(name) is not None


def has_env(var: str) -> bool:
    """Check if an environment variable is set and non-empty."""
    return bool(os.environ.get(var))


def skip_unless_engine(engine: str):
    """Pytest skip decorator: skip if the engine CLI is not installed."""
    binary = ENGINE_BINARIES.get(engine, engine)
    return pytest.mark.skipif(
        not has_binary(binary),
        reason=f"{binary} CLI not installed",
    )


def skip_unless_env(var: str):
    """Pytest skip decorator: skip if an env var is not set."""
    return pytest.mark.skipif(
        not has_env(var),
        reason=f"{var} env var not set",
    )


@pytest.fixture()
def e2e_workspace(tmp_path: Path) -> Path:
    """Create a minimal git repo with a buggy Python file.

    Yields the repo directory path. Cleanup is handled by tmp_path.
    """
    repo = tmp_path / "test-repo"
    repo.mkdir()

    # Init git repo with a commit
    subprocess.run(
        ["git", "init"], cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.email", "test@e2e.test"],
        cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "E2E Test"],
        cwd=repo, check=True, capture_output=True,
    )

    # Write the buggy file
    (repo / "math_utils.py").write_text(_BUGGY_FILE)

    subprocess.run(
        ["git", "add", "."], cwd=repo, check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "initial commit"],
        cwd=repo, check=True, capture_output=True,
    )

    return repo


@pytest.fixture()
def available_engines() -> dict[str, object]:
    """Return engine_name → adapter for engines with both CLI and API key available."""
    engines: dict[str, object] = {}
    for name, adapter_cls in ENGINE_ADAPTERS.items():
        binary = ENGINE_BINARIES[name]
        required_env = ENGINE_REQUIRED_ENV.get(name, "")
        if has_binary(binary) and has_env(required_env):
            engines[name] = adapter_cls()
    return engines
