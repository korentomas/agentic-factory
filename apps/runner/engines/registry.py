"""
Engine registry — maps engine names to adapter instances and selects
the best engine for a given model.
"""

from __future__ import annotations

import os

import structlog

from apps.orchestrator.providers import ENGINE_MODEL_AFFINITY
from apps.runner.engines.aider import AiderAdapter
from apps.runner.engines.claude_code import ClaudeCodeAdapter
from apps.runner.engines.codex import CodexAdapter
from apps.runner.engines.gemini_cli import GeminiCliAdapter
from apps.runner.engines.pi import PiAdapter
from apps.runner.engines.protocol import AgentEngine

logger = structlog.get_logger()


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


# Lazy registry — instantiated on first access.
_ENGINES: dict[str, AgentEngine] | None = None


def _build_registry() -> dict[str, AgentEngine]:
    """Build the engine registry. Called once."""
    return {
        "claude-code": ClaudeCodeAdapter(),
        "codex": CodexAdapter(),
        "gemini-cli": GeminiCliAdapter(),
        "aider": AiderAdapter(),
        "oh-my-pi": PiAdapter(),
    }


def get_registry() -> dict[str, AgentEngine]:
    """Return the engine registry, building it on first call."""
    global _ENGINES  # noqa: PLW0603
    if _ENGINES is None:
        _ENGINES = _build_registry()
    return _ENGINES


def get_engine(engine_name: str) -> AgentEngine:
    """Get an engine adapter by name.

    Args:
        engine_name: Engine identifier (e.g. "claude-code", "aider").

    Returns:
        The engine adapter instance.

    Raises:
        ValueError: If the engine name is unknown.
    """
    registry = get_registry()
    if engine_name not in registry:
        available = sorted(registry.keys())
        raise ValueError(
            f"Unknown engine {engine_name!r}. Available: {available}"
        )
    return registry[engine_name]


def select_engine(
    model: str | None = None,
    preferred_engine: str | None = None,
) -> AgentEngine:
    """Pick the best engine for a given model.

    Priority:
    1. Explicit engine override (preferred_engine or LAILATOV_ENGINE env var)
    2. Model affinity from ENGINE_MODEL_AFFINITY
    3. aider as universal fallback

    Args:
        model:            Model name (used to infer best engine).
        preferred_engine: Explicit engine override.

    Returns:
        The selected engine adapter.
    """
    # 1. Explicit override
    env_override = _get_env("LAILATOV_ENGINE")
    engine_name = preferred_engine or env_override

    if engine_name:
        logger.info("engine.select.override", engine=engine_name)
        return get_engine(engine_name)

    # 2. Model affinity matching
    if model:
        lower = model.lower()
        for prefix, affinity_engine in ENGINE_MODEL_AFFINITY:
            if lower.startswith(prefix):
                logger.info("engine.select.affinity", engine=affinity_engine, model=model)
                return get_engine(affinity_engine)

    # 3. Universal fallback
    logger.info("engine.select.fallback", engine="aider", model=model)
    return get_engine("aider")


def reset_registry() -> None:
    """Reset the engine registry. Used in tests."""
    global _ENGINES  # noqa: PLW0603
    _ENGINES = None
