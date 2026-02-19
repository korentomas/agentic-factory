"""
E2E smoke tests for engine adapters.

Each test verifies that a real CLI + real API key can execute a trivial
coding task. Tests skip gracefully when the CLI binary or API key is
unavailable.

Run:
    pytest tests/test_e2e_engines.py -v --tb=short -s --no-cov
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from apps.runner.benchmark import BenchmarkResult, BenchmarkSuite
from apps.runner.engines.aider import AiderAdapter
from apps.runner.engines.claude_code import ClaudeCodeAdapter
from apps.runner.engines.codex import CodexAdapter
from apps.runner.engines.gemini_cli import GeminiCliAdapter
from apps.runner.engines.pi import PiAdapter
from apps.runner.models import RunnerTask
from tests.conftest_e2e import E2E_PROMPT, skip_unless_engine, skip_unless_env

# Register fixtures from conftest_e2e so pytest can discover them.
pytest_plugins = ["tests.conftest_e2e"]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TIMEOUT = 60
_MAX_TURNS = 3


def _make_task(
    workspace: Path,
    *,
    model: str,
    engine: str,
    env_vars: dict[str, str] | None = None,
) -> RunnerTask:
    """Build a RunnerTask pointing at the e2e workspace."""
    task = RunnerTask(
        task_id="e2e-smoke",
        repo_url="local://test",
        branch="main",
        base_branch="main",
        title="Fix add() bug",
        description=E2E_PROMPT,
        engine=engine,
        model=model,
        max_turns=_MAX_TURNS,
        timeout_seconds=_TIMEOUT,
        env_vars=env_vars or {},
    )
    # Adapters read workspace_path via hasattr(); set on frozen dataclass.
    object.__setattr__(task, "workspace_path", workspace)
    return task


# ===========================================================================
# Phase 2.1 — Engine smoke tests (direct API keys)
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("claude-code")
@skip_unless_env("ANTHROPIC_API_KEY")
async def test_claude_code_smoke(e2e_workspace: Path) -> None:
    """Claude Code can execute a trivial fix with a real API key."""
    adapter = ClaudeCodeAdapter()
    task = _make_task(
        e2e_workspace, model="claude-haiku-4-5", engine="claude-code",
    )
    result = await adapter.run(task)

    assert result.status == "success", (
        f"Claude Code failed: {result.error_message}"
    )
    assert result.duration_ms > 0
    assert result.error_message is None


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("codex")
@skip_unless_env("OPENAI_API_KEY")
async def test_codex_smoke(e2e_workspace: Path) -> None:
    """Codex can execute a trivial fix with a real API key."""
    adapter = CodexAdapter()
    task = _make_task(
        e2e_workspace, model="gpt-4.1-mini", engine="codex",
    )
    result = await adapter.run(task)

    assert result.status == "success", (
        f"Codex failed: {result.error_message}"
    )
    assert result.duration_ms > 0
    assert result.error_message is None


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("gemini-cli")
@skip_unless_env("GEMINI_API_KEY")
async def test_gemini_cli_smoke(e2e_workspace: Path) -> None:
    """Gemini CLI can execute a trivial fix with a real API key."""
    adapter = GeminiCliAdapter()
    task = _make_task(
        e2e_workspace, model="gemini-2.5-flash", engine="gemini-cli",
    )
    result = await adapter.run(task)

    assert result.status == "success", (
        f"Gemini CLI failed: {result.error_message}"
    )
    assert result.duration_ms > 0
    assert result.error_message is None


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("aider")
@skip_unless_env("ANTHROPIC_API_KEY")
async def test_aider_smoke(e2e_workspace: Path) -> None:
    """Aider can execute a trivial fix with a real API key."""
    adapter = AiderAdapter()
    task = _make_task(
        e2e_workspace, model="claude-haiku-4-5", engine="aider",
    )
    result = await adapter.run(task)

    assert result.status == "success", (
        f"Aider failed: {result.error_message}"
    )
    assert result.duration_ms > 0
    assert result.error_message is None


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("oh-my-pi")
@skip_unless_env("OPENAI_API_KEY")
async def test_omp_smoke(e2e_workspace: Path) -> None:
    """oh-my-pi can execute a trivial fix with a real API key.

    Uses OpenAI provider because omp requires per-provider auth
    (not just env vars) for Anthropic models.
    """
    adapter = PiAdapter()
    task = _make_task(
        e2e_workspace, model="gpt-4.1-nano", engine="oh-my-pi",
    )
    result = await adapter.run(task)

    assert result.status == "success", (
        f"oh-my-pi failed: {result.error_message}"
    )
    assert result.duration_ms > 0
    assert result.error_message is None


# ===========================================================================
# Phase 2.2 — OpenRouter routing tests
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("claude-code")
@skip_unless_env("OPENROUTER_API_KEY")
async def test_claude_code_via_openrouter(e2e_workspace: Path) -> None:
    """Claude Code works when routed through OpenRouter."""
    openrouter_key = os.environ["OPENROUTER_API_KEY"]
    task = _make_task(
        e2e_workspace,
        model="claude-haiku-4-5",
        engine="claude-code",
        env_vars={
            "ANTHROPIC_API_KEY": "",
            "ANTHROPIC_BASE_URL": "https://openrouter.ai/api",
            "ANTHROPIC_AUTH_TOKEN": openrouter_key,
        },
    )
    adapter = ClaudeCodeAdapter()
    result = await adapter.run(task)

    assert result.status == "success", (
        f"Claude via OpenRouter failed: {result.error_message}"
    )
    assert result.duration_ms > 0


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("aider")
@skip_unless_env("OPENROUTER_API_KEY")
async def test_aider_via_openrouter(e2e_workspace: Path) -> None:
    """Aider works when routed through OpenRouter."""
    openrouter_key = os.environ["OPENROUTER_API_KEY"]
    task = _make_task(
        e2e_workspace,
        model="openrouter/anthropic/claude-haiku-4-5",
        engine="aider",
        env_vars={
            "OPENROUTER_API_KEY": openrouter_key,
        },
    )
    adapter = AiderAdapter()
    result = await adapter.run(task)

    assert result.status == "success", (
        f"Aider via OpenRouter failed: {result.error_message}"
    )
    assert result.duration_ms > 0


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("oh-my-pi")
@skip_unless_env("OPENAI_API_KEY")
async def test_omp_via_openai(e2e_workspace: Path) -> None:
    """oh-my-pi works with OpenAI provider (gpt-4.1-nano).

    omp does not support OpenRouter model routing — its model registry
    maps directly to native provider APIs. We test with OpenAI as the
    cheapest available path.
    """
    task = _make_task(
        e2e_workspace,
        model="gpt-4.1-nano",
        engine="oh-my-pi",
    )
    adapter = PiAdapter()
    result = await adapter.run(task)

    assert result.status == "success", (
        f"omp via OpenAI failed: {result.error_message}"
    )
    assert result.duration_ms > 0


# ===========================================================================
# Phase 3 — Multi-engine comparison
# ===========================================================================


@pytest.mark.e2e
@pytest.mark.slow
async def test_engine_comparison(
    e2e_workspace: Path,
    available_engines: dict[str, object],
) -> None:
    """Run the same task on all available engines and compare results."""
    if not available_engines:
        pytest.skip("No engine CLIs installed")

    suite = BenchmarkSuite()
    results_collected = 0

    for engine_name, adapter in available_engines.items():
        task = _make_task(
            e2e_workspace,
            model=_default_model_for_engine(engine_name),
            engine=engine_name,
        )
        result = await adapter.run(task)

        status = "pass" if result.status == "success" else "fail"
        suite.add_result(
            BenchmarkResult(
                instance_id="e2e-add-bug",
                engine=engine_name,
                model=task.model or "",
                status=status,
                duration_ms=result.duration_ms,
                cost_usd=result.cost_usd,
                error_message=result.error_message,
            )
        )
        results_collected += 1

    assert results_collected > 0, "No engines were tested"
    summary = suite.summary()
    assert summary["passed"] > 0, (
        f"No engines passed. Summary: {summary}"
    )


def _default_model_for_engine(engine_name: str) -> str:
    """Return the cheapest model for each engine."""
    return {
        "claude-code": "claude-haiku-4-5",
        "codex": "gpt-4.1-mini",
        "gemini-cli": "gemini-2.5-flash",
        "aider": "claude-haiku-4-5",
        "oh-my-pi": "gpt-4.1-nano",
    }.get(engine_name, "claude-haiku-4-5")
