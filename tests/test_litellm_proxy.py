"""Tests for LiteLLM proxy configuration module."""

import pytest

from apps.runner.litellm_proxy import (
    LiteLLMConfig,
    build_litellm_env,
    get_litellm_config,
    is_proxy_configured,
    resolve_model,
)

# -- get_litellm_config reads from env vars ----------------------------------


def test_config_reads_proxy_url_from_env(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://proxy:4000")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-test-key")
    monkeypatch.delenv("LITELLM_FALLBACK_MODELS", raising=False)

    config = get_litellm_config()

    assert config.proxy_url == "http://proxy:4000"
    assert config.api_key == "sk-test-key"


def test_config_defaults_when_env_vars_unset(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_FALLBACK_MODELS", raising=False)

    config = get_litellm_config()

    assert config.proxy_url == ""
    assert config.api_key == ""
    assert config.fallback_models == []
    assert config.timeout_seconds == 120
    assert config.max_retries == 2


# -- Fallback models parsing -------------------------------------------------


def test_fallback_models_parsed_from_comma_separated_string(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setenv(
        "LITELLM_FALLBACK_MODELS",
        "gpt-4o, claude-sonnet-4-6, deepseek/deepseek-chat",
    )

    config = get_litellm_config()

    assert config.fallback_models == [
        "gpt-4o",
        "claude-sonnet-4-6",
        "deepseek/deepseek-chat",
    ]


def test_fallback_models_empty_when_env_var_blank(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setenv("LITELLM_FALLBACK_MODELS", "")

    config = get_litellm_config()

    assert config.fallback_models == []


def test_fallback_models_strips_whitespace(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setenv("LITELLM_FALLBACK_MODELS", " gpt-4o , , claude-sonnet-4-6 ")

    config = get_litellm_config()

    assert config.fallback_models == ["gpt-4o", "claude-sonnet-4-6"]


# -- Model aliases via get_litellm_config ------------------------------------


def test_config_includes_default_model_aliases(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_FALLBACK_MODELS", raising=False)

    config = get_litellm_config()

    assert "fast" in config.model_aliases
    assert "premium" in config.model_aliases
    assert config.model_aliases["fast"] == "deepseek/deepseek-chat"
    assert config.model_aliases["premium"] == "claude-opus-4-6"


# -- resolve_model -----------------------------------------------------------


def test_resolve_model_with_alias_returns_target():
    config = LiteLLMConfig(
        model_aliases={"cheap": "deepseek/deepseek-chat"},
    )

    result = resolve_model(config, "cheap")

    assert result == "deepseek/deepseek-chat"


def test_resolve_model_without_alias_returns_original():
    config = LiteLLMConfig(model_aliases={})

    result = resolve_model(config, "gpt-4o")

    assert result == "gpt-4o"


# -- build_litellm_env -------------------------------------------------------


def test_build_litellm_env_with_proxy_configured():
    config = LiteLLMConfig(
        proxy_url="http://proxy:4000",
        api_key="sk-key-123",
    )

    env = build_litellm_env(config)

    assert env["OPENAI_API_BASE"] == "http://proxy:4000"
    assert env["OPENAI_API_KEY"] == "sk-key-123"


def test_build_litellm_env_omits_empty_values():
    config = LiteLLMConfig(proxy_url="", api_key="")

    env = build_litellm_env(config)

    assert "OPENAI_API_BASE" not in env
    assert "OPENAI_API_KEY" not in env


def test_build_litellm_env_partial_config():
    config = LiteLLMConfig(proxy_url="http://proxy:4000", api_key="")

    env = build_litellm_env(config)

    assert env["OPENAI_API_BASE"] == "http://proxy:4000"
    assert "OPENAI_API_KEY" not in env


# -- is_proxy_configured -----------------------------------------------------


def test_is_proxy_configured_returns_true_when_set(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_URL", "http://proxy:4000")

    assert is_proxy_configured() is True


def test_is_proxy_configured_returns_false_when_unset(monkeypatch):
    monkeypatch.delenv("LITELLM_PROXY_URL", raising=False)

    assert is_proxy_configured() is False


def test_is_proxy_configured_returns_false_when_empty(monkeypatch):
    monkeypatch.setenv("LITELLM_PROXY_URL", "")

    assert is_proxy_configured() is False


# -- Config immutability (frozen dataclass) ----------------------------------


def test_config_is_frozen():
    config = LiteLLMConfig(proxy_url="http://proxy:4000")

    with pytest.raises(AttributeError):
        config.proxy_url = "http://other:5000"  # type: ignore[misc]
