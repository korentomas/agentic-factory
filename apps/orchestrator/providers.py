"""
Provider and model configuration for AgentFactory.

Defines model tiers, provider configurations, and model resolution logic
for the multi-provider, multi-tier pipeline. This module does NOT read
env vars at import time — all reads happen at call time via ``_get_env()``.

Usage::

    from apps.orchestrator.providers import (
        get_model_for_stage,
        get_provider_config,
        derive_provider_from_model,
        ModelTier,
        PipelineStage,
    )

    model = get_model_for_stage(PipelineStage.WRITE, risk_tier="medium")
    provider = derive_provider_from_model(model)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Literal


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time, not import time."""
    return os.getenv(key, default)


class ModelTier(str, Enum):
    """Model capability tier — maps to cost/quality tradeoffs.

    FAST:     Haiku-class — cheap, good for classification and triage.
    STANDARD: Sonnet-class — balanced coding + reasoning.
    PREMIUM:  Opus-class — deep reasoning, thorough review.
    """

    FAST = "fast"
    STANDARD = "standard"
    PREMIUM = "premium"


class PipelineStage(str, Enum):
    """Stages in the AgentFactory pipeline."""

    TRIAGE = "triage"
    PLAN = "plan"
    WRITE = "write"
    REVIEW = "review"
    AUDIT = "audit"
    REMEDIATION = "remediation"
    EXTRACTION = "extraction"


# Default tier assignment per stage — optimizes for cost where quality allows.
STAGE_DEFAULT_TIER: dict[PipelineStage, ModelTier] = {
    PipelineStage.TRIAGE: ModelTier.FAST,
    PipelineStage.PLAN: ModelTier.PREMIUM,
    PipelineStage.WRITE: ModelTier.STANDARD,
    PipelineStage.REVIEW: ModelTier.PREMIUM,
    PipelineStage.AUDIT: ModelTier.STANDARD,
    PipelineStage.REMEDIATION: ModelTier.STANDARD,
    PipelineStage.EXTRACTION: ModelTier.FAST,
}

# Risk tier escalation: high-risk tasks escalate cheap models to avoid
# using Haiku for auth changes, migration reviews, etc.
RISK_TIER_ESCALATION: dict[str, dict[ModelTier, ModelTier]] = {
    "high": {
        ModelTier.FAST: ModelTier.STANDARD,
    },
    "medium": {},
    "low": {},
}

# Env var names for per-stage model override (matches GitHub Actions vars).
_STAGE_ENV_KEYS: dict[PipelineStage, str] = {
    PipelineStage.TRIAGE: "TRIAGE_MODEL",
    PipelineStage.PLAN: "PLAN_MODEL",
    PipelineStage.WRITE: "WRITE_MODEL",
    PipelineStage.REVIEW: "REVIEW_MODEL",
    PipelineStage.AUDIT: "AUDIT_MODEL",
    PipelineStage.REMEDIATION: "REMEDIATION_MODEL",
    PipelineStage.EXTRACTION: "EXTRACTION_MODEL",
}

# Legacy env var fallback by tier.
_LEGACY_ENV_KEYS: dict[ModelTier, str] = {
    ModelTier.FAST: "CLAUDE_SONNET_MODEL",
    ModelTier.STANDARD: "CLAUDE_SONNET_MODEL",
    ModelTier.PREMIUM: "CLAUDE_OPUS_MODEL",
}


@dataclass(frozen=True)
class ProviderConfig:
    """Configuration for an AI provider.

    Frozen (immutable) — provider configs are static reference data.

    Attributes:
        name:                   Human-readable provider name.
        base_url:               API base URL (empty string for Anthropic direct).
        api_key_env:            Env var name holding the API key.
        models_by_tier:         Mapping of ModelTier to default model name.
        supports_cost_tracking: Whether the provider returns cost data in responses.
    """

    name: str
    base_url: str
    api_key_env: str
    models_by_tier: dict[ModelTier, str]
    supports_cost_tracking: bool = True


# ── Built-in provider definitions ─────────────────────────────────────────────
PROVIDERS: dict[str, ProviderConfig] = {
    "anthropic": ProviderConfig(
        name="Anthropic Direct",
        base_url="",
        api_key_env="ANTHROPIC_API_KEY",
        models_by_tier={
            ModelTier.FAST: "claude-haiku-4-5",
            ModelTier.STANDARD: "claude-sonnet-4-6",
            ModelTier.PREMIUM: "claude-opus-4-6",
        },
        supports_cost_tracking=True,
    ),
    "openrouter": ProviderConfig(
        name="OpenRouter",
        base_url="https://openrouter.ai/api",
        api_key_env="OPENROUTER_API_KEY",
        models_by_tier={
            ModelTier.FAST: "anthropic/claude-haiku-4-5",
            ModelTier.STANDARD: "anthropic/claude-sonnet-4-6",
            ModelTier.PREMIUM: "anthropic/claude-opus-4-6",
        },
        supports_cost_tracking=False,
    ),
    "bedrock": ProviderConfig(
        name="Amazon Bedrock",
        base_url="",
        api_key_env="",
        models_by_tier={
            ModelTier.FAST: "claude-haiku-4-5",
            ModelTier.STANDARD: "claude-sonnet-4-6",
            ModelTier.PREMIUM: "claude-opus-4-6",
        },
        supports_cost_tracking=True,
    ),
    "vertex": ProviderConfig(
        name="Google Vertex AI",
        base_url="",
        api_key_env="",
        models_by_tier={
            ModelTier.FAST: "claude-haiku-4-5",
            ModelTier.STANDARD: "claude-sonnet-4-6",
            ModelTier.PREMIUM: "claude-opus-4-6",
        },
        supports_cost_tracking=True,
    ),
}


def get_provider_config(provider_name: str | None = None) -> ProviderConfig:
    """Get the configuration for a provider.

    If ``provider_name`` is None, reads from the ``AGENTFACTORY_PROVIDER``
    env var, defaulting to ``"anthropic"``.

    Args:
        provider_name: Provider name key (e.g. ``"anthropic"``, ``"openrouter"``).

    Returns:
        ProviderConfig for the specified provider.

    Raises:
        ValueError: If the provider name is unknown.
    """
    if provider_name is None:
        provider_name = _get_env("AGENTFACTORY_PROVIDER", "anthropic")

    provider_name = provider_name.lower().strip()

    if provider_name not in PROVIDERS:
        raise ValueError(
            f"Unknown provider {provider_name!r}. "
            f"Available: {sorted(PROVIDERS.keys())}"
        )
    return PROVIDERS[provider_name]


def get_model_for_stage(
    stage: PipelineStage,
    risk_tier: Literal["high", "medium", "low"] = "medium",
    provider_name: str | None = None,
) -> str:
    """Resolve the model name for a given pipeline stage and risk tier.

    Resolution order:

    1. Stage-specific env var (e.g. ``TRIAGE_MODEL``, ``WRITE_MODEL``)
    2. Legacy env var (``CLAUDE_SONNET_MODEL`` / ``CLAUDE_OPUS_MODEL``)
    3. Provider default for the appropriate model tier (with risk escalation)

    Args:
        stage:         Pipeline stage to resolve model for.
        risk_tier:     Risk tier of the current task (affects tier escalation).
        provider_name: Optional provider override.

    Returns:
        Model name string suitable for the ``--model`` CLI flag.
    """
    # 1. Check stage-specific env var
    stage_env_key = _STAGE_ENV_KEYS[stage]
    stage_override = _get_env(stage_env_key)
    if stage_override:
        return stage_override

    # 2. Check legacy env vars
    default_tier = STAGE_DEFAULT_TIER[stage]
    legacy_key = _LEGACY_ENV_KEYS[default_tier]
    legacy = _get_env(legacy_key)
    if legacy:
        return legacy

    # 3. Provider default with risk escalation
    provider = get_provider_config(provider_name)
    effective_tier = default_tier

    escalation = RISK_TIER_ESCALATION.get(risk_tier, {})
    if default_tier in escalation:
        effective_tier = escalation[default_tier]

    return provider.models_by_tier[effective_tier]


def derive_provider_from_model(model_name: str) -> str:
    """Infer the provider name from a model name string.

    Heuristic:

    - Model names with a ``/`` (e.g. ``anthropic/claude-sonnet-4-6``,
      ``deepseek/deepseek-chat``) indicate OpenRouter routing.
    - Bare model names (e.g. ``claude-sonnet-4-6``) indicate direct provider
      access — Anthropic by default, or Bedrock/Vertex based on env vars.

    Args:
        model_name: Model name, possibly with ``provider/`` prefix.

    Returns:
        Provider name string (e.g. ``"anthropic"``, ``"openrouter"``).
    """
    if "/" in model_name:
        return "openrouter"

    if _get_env("CLAUDE_CODE_USE_BEDROCK") == "1":
        return "bedrock"
    if _get_env("CLAUDE_CODE_USE_VERTEX") == "1":
        return "vertex"
    return "anthropic"
