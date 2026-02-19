# Coding Agent Engines

AgentFactory uses a composite action (`.github/actions/run-agent`) that dispatches to different coding agent engines. This page covers engine-specific setup.

## claude-code (default)

**Action:** `anthropics/claude-code-action@v1`
**Models:** Claude Opus, Sonnet, Haiku (Anthropic-native names)
**Cost tracking:** Yes (Anthropic direct only)

### Supported backends

| Backend | API Key | Settings |
|---------|---------|----------|
| Anthropic Direct | `ANTHROPIC_API_KEY` | None |
| OpenRouter | `OPENROUTER_API_KEY` | `{"env":{"ANTHROPIC_BASE_URL":"https://openrouter.ai/api"}}` |
| Amazon Bedrock | AWS credentials | `{"env":{"CLAUDE_CODE_USE_BEDROCK":"1"}}` |
| Google Vertex AI | GCP credentials | `{"env":{"CLAUDE_CODE_USE_VERTEX":"1"}}` |

### Model naming

Bare names for direct access, `provider/model` for OpenRouter:

```
claude-sonnet-4-6          # Anthropic direct
anthropic/claude-sonnet-4-6  # OpenRouter
```

See [providers.md](providers.md) for detailed backend setup.

## codex

**Action:** `openai/codex-action@v1`
**Models:** GPT-4.1, GPT-4.1-mini, o3, o3-mini
**Cost tracking:** No

### Setup

1. Add your OpenAI API key as a secret:

```
OPENAI_API_KEY=sk-...
```

2. Set engine and model vars:

```
WRITE_ENGINE=codex
WRITE_MODEL=gpt-4.1
```

### Sandbox modes

Codex runs in a sandboxed environment. The `sandbox` input controls permissions:

| Mode | Description |
|------|-------------|
| `workspace-write` (default) | Can read/write files in the workspace |
| `read-only` | Read-only access to workspace |
| `danger-full-access` | Full filesystem access (use with caution) |

### Non-OpenAI models via Codex

Codex supports alternative API endpoints. For DeepSeek or Qwen models, the composite action routes through codex with the appropriate API key.

**DeepSeek:**
```
WRITE_ENGINE=codex
WRITE_MODEL=deepseek-chat
DEEPSEEK_API_KEY=sk-...
```

**Qwen (Alibaba):**
```
WRITE_ENGINE=codex
WRITE_MODEL=qwen-coder-plus-latest
DASHSCOPE_API_KEY=sk-...
```

## gemini-cli

**Action:** `google-github-actions/run-gemini-cli@v1`
**Models:** Gemini 2.5 Flash, Gemini 2.5 Pro
**Cost tracking:** No
**Free tier:** Yes (via Google AI Studio API key)

### Setup

1. Get a free API key at [Google AI Studio](https://aistudio.google.com/apikey)

2. Add it as a secret:

```
GEMINI_API_KEY=AI...
```

3. Set engine and model vars:

```
TRIAGE_ENGINE=gemini-cli
TRIAGE_MODEL=gemini-2.5-flash
```

### Google Cloud / Vertex AI backend

For enterprise use with Vertex AI:

```
WRITE_ENGINE=gemini-cli
```

And configure Workload Identity Federation in the workflow (no API key needed):

```yaml
with:
  gcp_project_id: your-project-id
  gcp_location: us-central1
  gcp_workload_identity_provider: projects/123/locations/global/workloadIdentityPools/...
  use_vertex_ai: "true"
```

### Model naming

Gemini uses its own model names:

```
gemini-2.5-flash          # Fast, free tier
gemini-2.5-pro            # Premium reasoning
```

## Engine comparison

| Feature | claude-code | codex | gemini-cli |
|---------|-------------|-------|------------|
| Cost tracking | Yes (Anthropic direct) | No | No |
| Turn counting | Yes | No | No |
| Tool allowlisting | Yes | No | No |
| Sandbox modes | No | Yes | No |
| Free tier | No | No | Yes |
| Chinese model support | Via OpenRouter | Via API endpoint | No |
| Execution output file | Yes (NDJSON) | Yes (markdown) | No |
