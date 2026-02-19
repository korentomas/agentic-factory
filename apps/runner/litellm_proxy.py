"""LiteLLM proxy configuration for routing LLM calls.

Provides configuration, model resolution, and env-var injection
for engines that route through a LiteLLM proxy instance.  LiteLLM
exposes an OpenAI-compatible API, enabling unified cost tracking,
rate limiting, and automatic model fallbacks across providers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger()

# ---------------------------------------------------------------------------
# Default model aliases — map friendly names to provider/model IDs
# ---------------------------------------------------------------------------
_DEFAULT_MODEL_ALIASES: dict[str, str] = {
    "fast": "deepseek/deepseek-chat",
    "premium": "claude-opus-4-6",
    "balanced": "claude-sonnet-4-6",
}


def _get_env(key: str, default: str = "") -> str:
    """Read an environment variable at call time (never at import)."""
    return os.getenv(key, default)


# ---------------------------------------------------------------------------
# Configuration dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LiteLLMConfig:
    """Frozen configuration for a LiteLLM proxy connection.

    Attributes:
        proxy_url:        Base URL of the LiteLLM proxy server.
        api_key:          API key for authenticating with the proxy.
        model_aliases:    Friendly name -> model ID mapping.
        fallback_models:  Ordered list of fallback models if the primary fails.
        timeout_seconds:  Per-request timeout for proxy calls.
        max_retries:      Maximum retry count on transient failures.
    """

    proxy_url: str = ""
    api_key: str = ""
    model_aliases: dict[str, str] = field(default_factory=dict)
    fallback_models: list[str] = field(default_factory=list)
    timeout_seconds: int = 120
    max_retries: int = 2


# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------

def get_litellm_config() -> LiteLLMConfig:
    """Build a ``LiteLLMConfig`` from environment variables.

    Reads at call time:
    - ``LITELLM_PROXY_URL``       — proxy base URL
    - ``LITELLM_API_KEY``         — proxy authentication key
    - ``LITELLM_FALLBACK_MODELS`` — comma-separated fallback model list

    Returns:
        A frozen :class:`LiteLLMConfig` populated from the environment.
    """
    proxy_url = _get_env("LITELLM_PROXY_URL")
    api_key = _get_env("LITELLM_API_KEY")
    raw_fallbacks = _get_env("LITELLM_FALLBACK_MODELS")

    fallback_models: list[str] = []
    if raw_fallbacks:
        fallback_models = [m.strip() for m in raw_fallbacks.split(",") if m.strip()]

    config = LiteLLMConfig(
        proxy_url=proxy_url,
        api_key=api_key,
        model_aliases=dict(_DEFAULT_MODEL_ALIASES),
        fallback_models=fallback_models,
    )

    logger.debug(
        "litellm_proxy.config_loaded",
        proxy_url=config.proxy_url or "(not set)",
        fallback_count=len(config.fallback_models),
    )

    return config


def resolve_model(config: LiteLLMConfig, model_name: str) -> str:
    """Resolve a model name through the alias table.

    If *model_name* matches a key in ``config.model_aliases``, the
    corresponding model ID is returned.  Otherwise *model_name* is
    returned unchanged.

    Args:
        config:     LiteLLM configuration containing the alias mapping.
        model_name: Display name or raw model identifier.

    Returns:
        The resolved model identifier string.
    """
    resolved = config.model_aliases.get(model_name, model_name)
    if resolved != model_name:
        logger.debug(
            "litellm_proxy.model_resolved",
            alias=model_name,
            target=resolved,
        )
    return resolved


def build_litellm_env(config: LiteLLMConfig) -> dict[str, str]:
    """Build an env-var dict for subprocess engines routed through the proxy.

    LiteLLM exposes an OpenAI-compatible endpoint, so setting
    ``OPENAI_API_BASE`` and ``OPENAI_API_KEY`` causes most LLM
    libraries to route through the proxy transparently.

    Only non-empty values are included in the returned dict.

    Args:
        config: LiteLLM configuration to extract values from.

    Returns:
        Dictionary of environment variable name -> value.
    """
    env: dict[str, str] = {}

    if config.proxy_url:
        env["OPENAI_API_BASE"] = config.proxy_url
    if config.api_key:
        env["OPENAI_API_KEY"] = config.api_key

    return env


def is_proxy_configured() -> bool:
    """Check whether a LiteLLM proxy URL has been configured.

    Returns:
        ``True`` if the ``LITELLM_PROXY_URL`` environment variable is
        set to a non-empty value, ``False`` otherwise.
    """
    return bool(_get_env("LITELLM_PROXY_URL"))
