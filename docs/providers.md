# AI Provider Configuration

AgentFactory supports multiple AI providers. Choose based on your needs:

| Provider | Cost | Models | Setup |
|----------|------|--------|-------|
| **Anthropic Direct** | Standard pricing | Claude Opus, Sonnet | `ANTHROPIC_API_KEY` |
| **OpenRouter** | Often cheaper, many providers | Claude, DeepSeek, Gemini, Qwen, Llama | `OPENROUTER_API_KEY` |
| **Amazon Bedrock** | AWS billing | Claude models | AWS credentials |
| **Google Vertex AI** | GCP billing | Claude models | GCP credentials |

## Per-Stage Model Configuration

Each pipeline stage can use a different model. Set GitHub Actions variables (not secrets) to override:

| Variable | Stage | Default Tier | Default Model |
|----------|-------|-------------|---------------|
| `TRIAGE_MODEL` | Triage | Fast | `claude-sonnet-4-6` (via `CLAUDE_SONNET_MODEL`) |
| `PLAN_MODEL` | ExecPlan | Premium | `claude-opus-4-6` (via `CLAUDE_OPUS_MODEL`) |
| `WRITE_MODEL` | Write code | Standard | `claude-sonnet-4-6` (via `CLAUDE_SONNET_MODEL`) |
| `REVIEW_MODEL` | Code review | Premium | `claude-opus-4-6` (via `CLAUDE_OPUS_MODEL`) |
| `AUDIT_MODEL` | Spec audit | Premium | `claude-opus-4-6` (via `CLAUDE_OPUS_MODEL`) |
| `REMEDIATION_MODEL` | Remediation | Standard | `claude-sonnet-4-6` (via `CLAUDE_SONNET_MODEL`) |

### Fallback chain

Each stage uses a 3-level fallback: `STAGE_MODEL` → `CLAUDE_SONNET_MODEL` or `CLAUDE_OPUS_MODEL` → hardcoded default.

Example: if only `CLAUDE_SONNET_MODEL=claude-sonnet-4-5` is set, all Standard/Fast stages use Sonnet 4.5 without setting individual vars.

### Fallback models (optional)

If a primary model fails, a fallback model can retry the step:

| Variable | Stage |
|----------|-------|
| `TRIAGE_FALLBACK_MODEL` | Triage |
| `WRITE_FALLBACK_MODEL` | Write code |
| `REMEDIATION_FALLBACK_MODEL` | Remediation |

No fallback models are set by default. Review and audit stages don't need fallbacks — a review failure just means "needs human review."

### Backward compatibility

Existing deployments that only set `CLAUDE_SONNET_MODEL` and `CLAUDE_OPUS_MODEL` continue to work with zero changes. The per-stage vars are purely additive.

## Multi-Engine Support

AgentFactory now supports multiple coding agent engines, not just Claude Code. Each engine is a different GitHub Action that runs an AI coding agent:

| Engine | GitHub Action | Models | Cost Tracking |
|--------|--------------|--------|---------------|
| **claude-code** (default) | `anthropics/claude-code-action@v1` | Claude family, any Anthropic-compatible API | Yes |
| **codex** | `openai/codex-action@v1` | GPT-4.1, o3, DeepSeek, Qwen | No |
| **gemini-cli** | `google-github-actions/run-gemini-cli@v1` | Gemini 2.5 Flash/Pro | No |

### Per-stage engine configuration

Each pipeline stage can use a different engine. Set GitHub Actions variables:

| Variable | Stage | Default |
|----------|-------|---------|
| `TRIAGE_ENGINE` | Triage | `claude-code` |
| `PLAN_ENGINE` | ExecPlan | `claude-code` |
| `WRITE_ENGINE` | Code writing | `claude-code` |
| `REVIEW_ENGINE` | Code review | `claude-code` |
| `AUDIT_ENGINE` | Spec audit | `claude-code` |
| `REMEDIATION_ENGINE` | Remediation | `claude-code` |

### Example: mixed engine setup

Use Gemini for triage (free tier), Codex for writing, Claude for review:

```
TRIAGE_ENGINE=gemini-cli
TRIAGE_MODEL=gemini-2.5-flash

WRITE_ENGINE=codex
WRITE_MODEL=gpt-4.1

REVIEW_ENGINE=claude-code
REVIEW_MODEL=claude-opus-4-6
```

### Backward compatibility

With no `*_ENGINE` vars set, all workflows use `claude-code` exactly as before. The engine vars are purely additive.

See [engines.md](engines.md) for engine-specific setup guides.

## Anthropic Direct (default)

Set one secret in your GitHub Actions:

```
ANTHROPIC_API_KEY=sk-ant-...
```

No other configuration needed. Workflows use Claude Sonnet for coding and Opus for review by default.

## OpenRouter

OpenRouter lets you route through 200+ models from many providers — often at lower cost than direct API access. Use any model that supports tool use.

### Setup

1. Get an API key at [openrouter.ai/keys](https://openrouter.ai/keys)
2. Add secrets to your GitHub repo:

```
OPENROUTER_API_KEY=sk-or-v1-...
```

3. In your workflows, set the `settings` input on `claude-code-action`:

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    anthropic_api_key: ${{ secrets.OPENROUTER_API_KEY }}
    settings: |
      {
        "env": {
          "ANTHROPIC_BASE_URL": "https://openrouter.ai/api"
        }
      }
    claude_args: "--model anthropic/claude-sonnet-4-6 --max-turns 40"
```

### Model selection with OpenRouter

OpenRouter uses `provider/model` format. Update `claude_args` in your workflows:

**Coding agent (action-biased, fast):**
```yaml
claude_args: "--model anthropic/claude-sonnet-4-6 --max-turns 40"
# Or cheaper alternatives:
claude_args: "--model deepseek/deepseek-chat --max-turns 40"
claude_args: "--model google/gemini-2.5-flash --max-turns 40"
```

**Review agent (reasoning-biased, thorough):**
```yaml
claude_args: "--model anthropic/claude-opus-4-6 --max-turns 15"
# Or cheaper alternatives:
claude_args: "--model google/gemini-2.5-pro --max-turns 15"
claude_args: "--model qwen/qwen3-max-thinking --max-turns 15"
```

### Recommended cost-optimized setup

For teams optimizing cost, use cheaper models for writing and save Opus for review:

| Workflow | Model | Approx. cost/PR |
|----------|-------|-----------------|
| agent-write | `deepseek/deepseek-chat` | ~$0.02 |
| agent-review | `anthropic/claude-opus-4-6` | ~$0.15 |
| spec-audit | `google/gemini-2.5-flash` | ~$0.01 |
| agent-remediation | `deepseek/deepseek-chat` | ~$0.02 |
| **Total** | | **~$0.20/PR** |

vs. Anthropic direct (all Claude): ~$0.50–1.00/PR

### Environment variable reference

| Variable | Purpose |
|----------|---------|
| `ANTHROPIC_BASE_URL` | Point Claude Code at OpenRouter (or any Anthropic-compatible gateway) |
| `ANTHROPIC_API_KEY` | API key (OpenRouter key works here) |
| `OPENROUTER_API_KEY` | Alternative key name (set as `anthropic_api_key` in the action) |

## Amazon Bedrock

See the [claude-code-action cloud providers docs](https://github.com/anthropics/claude-code-action/blob/main/docs/cloud-providers.md).

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    settings: |
      {
        "env": {
          "CLAUDE_CODE_USE_BEDROCK": "1",
          "AWS_REGION": "us-east-1"
        }
      }
    claude_args: "--max-turns 40"
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
```

## Google Vertex AI

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    settings: |
      {
        "env": {
          "CLAUDE_CODE_USE_VERTEX": "1",
          "CLOUD_ML_REGION": "us-east5",
          "ANTHROPIC_VERTEX_PROJECT_ID": "your-project-id"
        }
      }
    claude_args: "--max-turns 40"
```

## Custom / Self-Hosted LLM Gateway

Any gateway that speaks the Anthropic Messages API format works:

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    anthropic_api_key: ${{ secrets.GATEWAY_API_KEY }}
    settings: |
      {
        "env": {
          "ANTHROPIC_BASE_URL": "https://your-gateway.internal.company.com"
        }
      }
```

Compatible gateways: LiteLLM, Portkey, Helicone, OpenRouter, any Anthropic-format proxy.
