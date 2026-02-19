"""
Tests for the provider configuration module.

Verifies model resolution logic, provider config lookup,
tier escalation, engine support, and provider inference from model names.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from apps.orchestrator.providers import (
    PROVIDERS,
    RISK_TIER_ESCALATION,
    STAGE_DEFAULT_TIER,
    ModelTier,
    PipelineStage,
    derive_provider_from_model,
    get_engine_for_stage,
    get_model_for_stage,
    get_provider_config,
)

# ── ProviderConfig ────────────────────────────────────────────────────────────


class TestProviderConfig:
    """ProviderConfig dataclass behavior."""

    def test_frozen_dataclass(self) -> None:
        """ProviderConfig is immutable after creation."""
        config = PROVIDERS["anthropic"]
        with pytest.raises(AttributeError):
            config.name = "modified"  # type: ignore[misc]

    def test_anthropic_config_has_all_tiers(self) -> None:
        """Anthropic provider defines models for every tier."""
        config = PROVIDERS["anthropic"]
        for tier in ModelTier:
            assert tier in config.models_by_tier

    def test_anthropic_supports_cost_tracking(self) -> None:
        """Anthropic direct supports cost tracking."""
        assert PROVIDERS["anthropic"].supports_cost_tracking is True

    def test_openrouter_does_not_support_cost_tracking(self) -> None:
        """OpenRouter returns cost: null — no cost tracking."""
        assert PROVIDERS["openrouter"].supports_cost_tracking is False


# ── ModelTier ─────────────────────────────────────────────────────────────────


class TestModelTier:
    """ModelTier enum values."""

    def test_enum_values(self) -> None:
        assert ModelTier.FAST == "fast"
        assert ModelTier.STANDARD == "standard"
        assert ModelTier.PREMIUM == "premium"

    def test_three_tiers_exist(self) -> None:
        assert len(ModelTier) == 3


# ── PipelineStage ─────────────────────────────────────────────────────────────


class TestPipelineStage:
    """PipelineStage enum completeness."""

    def test_all_stages_have_default_tier(self) -> None:
        """Every pipeline stage must have a default tier assignment."""
        for stage in PipelineStage:
            assert stage in STAGE_DEFAULT_TIER, f"Missing default tier for {stage}"

    def test_seven_stages_exist(self) -> None:
        assert len(PipelineStage) == 7


# ── get_provider_config ───────────────────────────────────────────────────────


class TestGetProviderConfig:
    """Provider config lookup."""

    def test_anthropic_is_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no env var or argument, returns Anthropic."""
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        config = get_provider_config()
        assert config.name == "Anthropic Direct"

    def test_reads_from_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Reads provider name from AGENTFACTORY_PROVIDER env var."""
        monkeypatch.setenv("AGENTFACTORY_PROVIDER", "openrouter")
        config = get_provider_config()
        assert config.name == "OpenRouter"

    def test_explicit_argument_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Explicit provider_name argument takes precedence over env var."""
        monkeypatch.setenv("AGENTFACTORY_PROVIDER", "openrouter")
        config = get_provider_config("anthropic")
        assert config.name == "Anthropic Direct"

    def test_unknown_provider_raises_value_error(self) -> None:
        """Unknown provider name raises ValueError with available list."""
        with pytest.raises(ValueError, match="Unknown provider"):
            get_provider_config("nonexistent")

    def test_case_insensitive_lookup(self) -> None:
        """Provider names are case-insensitive."""
        config = get_provider_config("OpenRouter")
        assert config.name == "OpenRouter"

    def test_whitespace_stripped(self) -> None:
        """Leading/trailing whitespace in provider name is stripped."""
        config = get_provider_config("  bedrock  ")
        assert config.name == "Amazon Bedrock"

    def test_all_providers_have_all_tiers(self) -> None:
        """Every built-in provider defines models for every tier."""
        for provider_name, config in PROVIDERS.items():
            for tier in ModelTier:
                assert tier in config.models_by_tier, (
                    f"Provider {provider_name!r} missing tier {tier}"
                )


# ── get_model_for_stage ───────────────────────────────────────────────────────


class TestGetModelForStage:
    """Model resolution logic — stage env var → legacy var → provider default."""

    def test_stage_env_var_takes_precedence(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WRITE_MODEL env var overrides everything else."""
        monkeypatch.setenv("WRITE_MODEL", "deepseek/deepseek-chat")
        monkeypatch.setenv("CLAUDE_SONNET_MODEL", "claude-sonnet-4-5")
        model = get_model_for_stage(PipelineStage.WRITE)
        assert model == "deepseek/deepseek-chat"

    def test_legacy_sonnet_var_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to CLAUDE_SONNET_MODEL for STANDARD/FAST-tier stages."""
        monkeypatch.delenv("WRITE_MODEL", raising=False)
        monkeypatch.setenv("CLAUDE_SONNET_MODEL", "claude-sonnet-4-5")
        model = get_model_for_stage(PipelineStage.WRITE)
        assert model == "claude-sonnet-4-5"

    def test_legacy_opus_var_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Falls back to CLAUDE_OPUS_MODEL for PREMIUM-tier stages."""
        monkeypatch.delenv("REVIEW_MODEL", raising=False)
        monkeypatch.setenv("CLAUDE_OPUS_MODEL", "claude-opus-4-5")
        model = get_model_for_stage(PipelineStage.REVIEW)
        assert model == "claude-opus-4-5"

    def test_provider_default_when_no_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """With no env vars, returns provider default for the stage's tier."""
        monkeypatch.delenv("WRITE_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_SONNET_MODEL", raising=False)
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        model = get_model_for_stage(PipelineStage.WRITE)
        assert model == "claude-sonnet-4-6"

    def test_triage_stage_uses_fast_tier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Triage defaults to FAST tier (Haiku)."""
        monkeypatch.delenv("TRIAGE_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_SONNET_MODEL", raising=False)
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        model = get_model_for_stage(PipelineStage.TRIAGE)
        assert model == "claude-haiku-4-5"

    def test_review_stage_uses_premium_tier(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Review defaults to PREMIUM tier (Opus)."""
        monkeypatch.delenv("REVIEW_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_OPUS_MODEL", raising=False)
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        model = get_model_for_stage(PipelineStage.REVIEW)
        assert model == "claude-opus-4-6"

    def test_high_risk_escalates_fast_to_standard(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """High-risk tasks escalate FAST tier to STANDARD (no Haiku for auth)."""
        monkeypatch.delenv("TRIAGE_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_SONNET_MODEL", raising=False)
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        model = get_model_for_stage(PipelineStage.TRIAGE, risk_tier="high")
        assert model == "claude-sonnet-4-6"

    def test_medium_risk_no_escalation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Medium-risk keeps default tier — no escalation."""
        monkeypatch.delenv("TRIAGE_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_SONNET_MODEL", raising=False)
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        model = get_model_for_stage(PipelineStage.TRIAGE, risk_tier="medium")
        assert model == "claude-haiku-4-5"

    def test_low_risk_no_escalation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Low-risk keeps default tier — no escalation."""
        monkeypatch.delenv("TRIAGE_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_SONNET_MODEL", raising=False)
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        model = get_model_for_stage(PipelineStage.TRIAGE, risk_tier="low")
        assert model == "claude-haiku-4-5"

    def test_openrouter_provider_returns_prefixed_model(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OpenRouter provider returns models with provider/ prefix."""
        monkeypatch.delenv("WRITE_MODEL", raising=False)
        monkeypatch.delenv("CLAUDE_SONNET_MODEL", raising=False)
        model = get_model_for_stage(
            PipelineStage.WRITE, provider_name="openrouter"
        )
        assert model == "anthropic/claude-sonnet-4-6"

    def test_stage_override_ignores_risk_escalation(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stage env var override is used as-is, no risk escalation applied."""
        monkeypatch.setenv("TRIAGE_MODEL", "claude-haiku-4-5")
        model = get_model_for_stage(PipelineStage.TRIAGE, risk_tier="high")
        assert model == "claude-haiku-4-5"

    def test_all_stages_resolve_without_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Every pipeline stage resolves to a valid model name."""
        # Clear all overrides
        for env_key in (
            "TRIAGE_MODEL", "PLAN_MODEL", "WRITE_MODEL",
            "REVIEW_MODEL", "AUDIT_MODEL", "REMEDIATION_MODEL",
            "EXTRACTION_MODEL", "CLAUDE_SONNET_MODEL", "CLAUDE_OPUS_MODEL",
            "AGENTFACTORY_PROVIDER",
        ):
            monkeypatch.delenv(env_key, raising=False)

        for stage in PipelineStage:
            model = get_model_for_stage(stage)
            assert isinstance(model, str)
            assert len(model) > 0


# ── derive_provider_from_model ────────────────────────────────────────────────


class TestDeriveProviderFromModel:
    """Provider inference from model name string."""

    def test_bare_model_is_anthropic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Bare model names default to Anthropic."""
        monkeypatch.delenv("CLAUDE_CODE_USE_BEDROCK", raising=False)
        monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
        assert derive_provider_from_model("claude-sonnet-4-6") == "anthropic"

    def test_slashed_model_is_openrouter(self) -> None:
        """Models with provider/ prefix indicate OpenRouter."""
        assert derive_provider_from_model("anthropic/claude-sonnet-4-6") == "openrouter"
        assert derive_provider_from_model("deepseek/deepseek-chat") == "openrouter"
        assert derive_provider_from_model("google/gemini-2.5-flash") == "openrouter"

    def test_bedrock_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLAUDE_CODE_USE_BEDROCK=1 overrides bare model to bedrock."""
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.delenv("CLAUDE_CODE_USE_VERTEX", raising=False)
        assert derive_provider_from_model("claude-sonnet-4-6") == "bedrock"

    def test_vertex_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """CLAUDE_CODE_USE_VERTEX=1 overrides bare model to vertex."""
        monkeypatch.delenv("CLAUDE_CODE_USE_BEDROCK", raising=False)
        monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
        assert derive_provider_from_model("claude-sonnet-4-6") == "vertex"

    def test_bedrock_takes_precedence_over_vertex(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """If both Bedrock and Vertex are set, Bedrock wins (checked first)."""
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        monkeypatch.setenv("CLAUDE_CODE_USE_VERTEX", "1")
        assert derive_provider_from_model("claude-sonnet-4-6") == "bedrock"

    def test_slashed_model_ignores_env_vars(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Slash in model name means OpenRouter regardless of env vars."""
        monkeypatch.setenv("CLAUDE_CODE_USE_BEDROCK", "1")
        assert derive_provider_from_model("anthropic/claude-sonnet-4-6") == "openrouter"

    def test_gpt_model_is_openai(self) -> None:
        """gpt-* models map to openai provider."""
        assert derive_provider_from_model("gpt-4.1") == "openai"
        assert derive_provider_from_model("gpt-4.1-mini") == "openai"

    def test_o3_model_is_openai(self) -> None:
        """o3* models map to openai provider."""
        assert derive_provider_from_model("o3") == "openai"
        assert derive_provider_from_model("o3-mini") == "openai"

    def test_o1_model_is_openai(self) -> None:
        """o1-* models map to openai provider."""
        assert derive_provider_from_model("o1-preview") == "openai"

    def test_gemini_model_is_google(self) -> None:
        """gemini-* models map to google provider."""
        assert derive_provider_from_model("gemini-2.5-flash") == "google"
        assert derive_provider_from_model("gemini-2.5-pro") == "google"

    def test_deepseek_model_is_deepseek(self) -> None:
        """deepseek-* models map to deepseek provider."""
        assert derive_provider_from_model("deepseek-chat") == "deepseek"
        assert derive_provider_from_model("deepseek-reasoner") == "deepseek"

    def test_qwen_model_is_qwen(self) -> None:
        """qwen-* models map to qwen provider."""
        assert derive_provider_from_model("qwen-max-latest") == "qwen"
        assert derive_provider_from_model("qwen-coder-plus-latest") == "qwen"

    def test_slashed_non_anthropic_still_openrouter(self) -> None:
        """Slash in model name always means OpenRouter, even for non-Anthropic."""
        assert derive_provider_from_model("openai/gpt-4.1") == "openrouter"
        assert derive_provider_from_model("google/gemini-2.5-flash") == "openrouter"


# ── Engine support ────────────────────────────────────────────────────────────


class TestProviderEngineField:
    """Engine field on ProviderConfig."""

    def test_all_providers_have_engine_field(self) -> None:
        """Every provider has a non-empty engine field."""
        for name, config in PROVIDERS.items():
            assert config.engine, f"Provider {name!r} has empty engine"
            assert config.engine in ("claude-code", "codex", "gemini-cli"), (
                f"Provider {name!r} has unknown engine {config.engine!r}"
            )

    def test_anthropic_engine_is_claude_code(self) -> None:
        """Anthropic uses claude-code engine."""
        assert PROVIDERS["anthropic"].engine == "claude-code"

    def test_openrouter_engine_is_claude_code(self) -> None:
        """OpenRouter uses claude-code engine (Anthropic-compatible gateway)."""
        assert PROVIDERS["openrouter"].engine == "claude-code"

    def test_openai_engine_is_codex(self) -> None:
        """OpenAI uses codex engine."""
        assert PROVIDERS["openai"].engine == "codex"

    def test_google_engine_is_gemini_cli(self) -> None:
        """Google AI uses gemini-cli engine."""
        assert PROVIDERS["google"].engine == "gemini-cli"

    def test_deepseek_engine_is_codex(self) -> None:
        """DeepSeek uses codex engine."""
        assert PROVIDERS["deepseek"].engine == "codex"

    def test_qwen_engine_is_codex(self) -> None:
        """Qwen uses codex engine."""
        assert PROVIDERS["qwen"].engine == "codex"


class TestNewProviderConfigs:
    """New provider configurations have correct tiers."""

    def test_openai_provider_config_tiers(self) -> None:
        """OpenAI provider has all tiers populated."""
        config = PROVIDERS["openai"]
        assert config.models_by_tier[ModelTier.FAST] == "gpt-4.1-mini"
        assert config.models_by_tier[ModelTier.STANDARD] == "gpt-4.1"
        assert config.models_by_tier[ModelTier.PREMIUM] == "o3"

    def test_google_provider_config_tiers(self) -> None:
        """Google provider has all tiers populated."""
        config = PROVIDERS["google"]
        assert config.models_by_tier[ModelTier.FAST] == "gemini-2.5-flash"
        assert config.models_by_tier[ModelTier.PREMIUM] == "gemini-2.5-pro"

    def test_deepseek_provider_config_tiers(self) -> None:
        """DeepSeek provider has all tiers populated."""
        config = PROVIDERS["deepseek"]
        assert config.models_by_tier[ModelTier.FAST] == "deepseek-chat"
        assert config.models_by_tier[ModelTier.PREMIUM] == "deepseek-reasoner"

    def test_qwen_provider_config_tiers(self) -> None:
        """Qwen provider has all tiers populated."""
        config = PROVIDERS["qwen"]
        assert config.models_by_tier[ModelTier.FAST] == "qwen-coder-plus-latest"
        assert config.models_by_tier[ModelTier.PREMIUM] == "qwen-max-latest"

    def test_new_providers_do_not_support_cost_tracking(self) -> None:
        """Non-Anthropic providers don't support cost tracking."""
        for name in ("openai", "google", "deepseek", "qwen"):
            assert PROVIDERS[name].supports_cost_tracking is False, (
                f"Provider {name!r} should not support cost tracking"
            )


class TestGetEngineForStage:
    """Engine resolution per pipeline stage."""

    def test_default_returns_provider_engine(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """With no env override, returns the provider's default engine."""
        monkeypatch.delenv("WRITE_ENGINE", raising=False)
        monkeypatch.delenv("AGENTFACTORY_PROVIDER", raising=False)
        engine = get_engine_for_stage(PipelineStage.WRITE)
        assert engine == "claude-code"

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """WRITE_ENGINE env var overrides provider default."""
        monkeypatch.setenv("WRITE_ENGINE", "codex")
        engine = get_engine_for_stage(PipelineStage.WRITE)
        assert engine == "codex"

    def test_triage_engine_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """TRIAGE_ENGINE env var works for triage stage."""
        monkeypatch.setenv("TRIAGE_ENGINE", "gemini-cli")
        engine = get_engine_for_stage(PipelineStage.TRIAGE)
        assert engine == "gemini-cli"

    def test_provider_openai_returns_codex(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """OpenAI provider returns codex engine by default."""
        monkeypatch.delenv("WRITE_ENGINE", raising=False)
        engine = get_engine_for_stage(PipelineStage.WRITE, provider_name="openai")
        assert engine == "codex"

    def test_provider_google_returns_gemini_cli(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Google provider returns gemini-cli engine by default."""
        monkeypatch.delenv("REVIEW_ENGINE", raising=False)
        engine = get_engine_for_stage(PipelineStage.REVIEW, provider_name="google")
        assert engine == "gemini-cli"

    def test_env_override_beats_provider(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Stage env var takes precedence over provider's engine."""
        monkeypatch.setenv("WRITE_ENGINE", "gemini-cli")
        engine = get_engine_for_stage(PipelineStage.WRITE, provider_name="openai")
        assert engine == "gemini-cli"


# ── RISK_TIER_ESCALATION ──────────────────────────────────────────────────────


class TestRiskTierEscalation:
    """Risk tier escalation rules."""

    def test_high_risk_escalates_fast(self) -> None:
        """High risk: FAST → STANDARD."""
        assert RISK_TIER_ESCALATION["high"][ModelTier.FAST] == ModelTier.STANDARD

    def test_high_risk_does_not_escalate_standard(self) -> None:
        """High risk: STANDARD stays STANDARD (not in escalation map)."""
        assert ModelTier.STANDARD not in RISK_TIER_ESCALATION["high"]

    def test_medium_risk_no_escalation(self) -> None:
        """Medium risk: no escalation rules."""
        assert len(RISK_TIER_ESCALATION["medium"]) == 0

    def test_low_risk_no_escalation(self) -> None:
        """Low risk: no escalation rules."""
        assert len(RISK_TIER_ESCALATION["low"]) == 0


# ── Metrics endpoint ──────────────────────────────────────────────────────────


def test_metrics_exposes_model_invocations_total(client: TestClient) -> None:
    """GET /metrics exposes model_invocations_total counter."""
    response = client.get("/metrics")
    assert "model_invocations_total" in response.text
