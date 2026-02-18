# AI Provider Configuration

AgentFactory supports multiple AI providers. Choose based on your needs:

| Provider | Cost | Models | Setup |
|----------|------|--------|-------|
| **Anthropic Direct** | Standard pricing | Claude Opus, Sonnet | `ANTHROPIC_API_KEY` |
| **OpenRouter** | Often cheaper, many providers | Claude, DeepSeek, Gemini, Qwen, Llama | `OPENROUTER_API_KEY` |
| **Amazon Bedrock** | AWS billing | Claude models | AWS credentials |
| **Google Vertex AI** | GCP billing | Claude models | GCP credentials |

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
