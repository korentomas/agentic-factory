<p align="center">
  <h1 align="center">AgentFactory</h1>
  <p align="center">
    <strong>Your tickets become pull requests. Automatically.</strong>
  </p>
  <p align="center">
    <a href="https://github.com/korentomas/agentic-factory/actions"><img src="https://github.com/korentomas/agentic-factory/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
    <a href="https://github.com/korentomas/agentic-factory/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
    <img src="https://img.shields.io/badge/python-3.12+-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12+">
    <img src="https://img.shields.io/badge/Claude_Code-powered-cc785c.svg" alt="Claude Code">
  </p>
</p>

AgentFactory is an open-source autonomous code factory. Tag a GitHub Issue or ClickUp ticket with `ai-agent`, and it triages the request, writes the code, opens a draft PR, reviews it, remediates findings, and promotes it to ready — without a human writing a single line of code.

It's like Copilot Workspace meets CodeRabbit, but fully autonomous and self-improving.

---

## Features

- **Three-stage pipeline** — Triage (evaluate clarity, ask questions) &rarr; Execute (write code, open PR) &rarr; Review (risk gate, tests, spec audit)
- **Self-improving** — Logs outcomes, extracts patterns weekly, learns from its own successes and failures
- **Risk-tiered review** — File-path-based risk policy (high/medium/low) with configurable review gates
- **Auto-remediation** — Automatically fixes review findings (up to 2 rounds, then escalates)
- **Multi-provider** — Anthropic Direct, OpenRouter (DeepSeek, Gemini, Llama), AWS Bedrock, Google Vertex
- **GitHub-native** — Works with just GitHub Actions + a GitHub App. No external services required
- **Request tracing** — Every request tagged with a UUID, propagated through structured logs
- **Cost tracking** — Per-PR cost, turn count, and duration displayed in every PR body

---

## How It Works

```
  GitHub Issue labeled "ai-agent"
  (or ClickUp ticket tagged "ai-agent")
              │
              ▼
  ┌─────────────────────────┐
  │     TRIAGE               │  Claude evaluates clarity.
  │     agent-triage.yml     │  Clear → dispatch.
  │                          │  Unclear → ask question, wait for reply.
  └────────────┬─────────────┘
               │
      ┌────────┴────────┐
      │                 │
   UNCLEAR            CLEAR
      │                 │
      ▼                 ▼
  Post question     ┌─────────────────────────┐
  on issue,         │     WRITE               │  Claude writes code,
  wait for reply,   │     agent-write.yml     │  runs tests, opens
  then re-triage    │                         │  draft PR on agent/* branch
                    └────────────┬────────────┘
                                 │
                                 ▼
                    ┌─────────────────────────┐
                    │     REVIEW              │  Risk gate → test suite →
                    │     agent-review.yml    │  Claude review + spec audit
                    │                         │  → outcome logged to JSONL
                    └────────────┬────────────┘
                                 │
                        ┌────────┴────────┐
                        │                 │
                     FINDINGS           CLEAN
                        │                 │
                        ▼                 ▼
                    REMEDIATE         PR marked ready
                    agent-            for review ✓
                    remediation.yml
                    (max 2 rounds,
                     then Slack
                     escalation)
```

---

## Quickstart

### Option A: GitHub Issues (simplest)

No orchestrator, no webhooks, no external services. Pure GitHub-native.

**1. Clone and set up**

```bash
git clone https://github.com/korentomas/agentic-factory.git
cd agentic-factory
```

**2. Copy workflow files to your target repo**

```bash
cp .github/workflows/*.yml /path/to/your-repo/.github/workflows/
cp -r .claude/ /path/to/your-repo/.claude/
cp risk-policy.json /path/to/your-repo/
cp ARCHITECTURE.md /path/to/your-repo/
cp CLAUDE.md /path/to/your-repo/
```

**3. Create a GitHub App**

Create a [GitHub App](https://docs.github.com/en/apps/creating-github-apps) with these permissions:

| Permission | Access |
|-----------|--------|
| Contents | Read & Write |
| Pull requests | Read & Write |
| Issues | Read & Write |

Install it on your target repo, then add these **GitHub Actions secrets**:

| Secret | Required | Description |
|--------|----------|-------------|
| `APP_ID` | Yes | Your GitHub App's ID |
| `APP_PRIVATE_KEY` | Yes | The app's private key (`.pem` contents) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key (or OpenRouter key) |
| `SLACK_WEBHOOK_URL` | No | Slack incoming webhook for escalation notifications |

> The workflows use [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token) to generate short-lived tokens scoped to the installation. More secure than PATs.

**4. Create an issue and add the `ai-agent` label**

That's it. The pipeline handles everything from there.

### Option B: ClickUp Integration

Requires deploying the orchestrator service.

**1. Deploy the orchestrator**

```bash
# Cloud Run
gcloud run deploy agent-factory \
  --source . \
  --region us-central1 \
  --set-env-vars CLICKUP_WEBHOOK_SECRET=...,CLICKUP_API_TOKEN=...,SLACK_WEBHOOK_URL=...

# Or locally
pip install -e .
uvicorn apps.orchestrator.main:app --port 8080
```

**2. Register the ClickUp webhook**

```bash
curl -X POST "https://api.clickup.com/api/v2/team/YOUR_TEAM_ID/webhook" \
  -H "Authorization: YOUR_CLICKUP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://YOUR_ORCHESTRATOR_URL/webhooks/clickup",
    "events": ["taskTagUpdated"]
  }'
```

**3. Tag any ClickUp ticket with `ai-agent`**

The orchestrator dispatches to the same GitHub Actions pipeline.

### Using OpenRouter or Other Providers

Add one more secret to use any model on OpenRouter:

```
CLAUDE_SETTINGS = {"env":{"ANTHROPIC_BASE_URL":"https://openrouter.ai/api"}}
```

Set `ANTHROPIC_API_KEY` to your OpenRouter key (`sk-or-v1-...`). This unlocks DeepSeek, Gemini, Qwen, Llama, and anything else on OpenRouter.

See [docs/providers.md](docs/providers.md) for Bedrock, Vertex, and custom gateway configuration.

---

## Architecture

```
agentic-factory/
├── apps/orchestrator/              # FastAPI service (Cloud Run)
│   ├── main.py                     # Webhook ingress, request ID middleware
│   ├── models.py                   # AgentTask — parse at the boundary
│   ├── routers/
│   │   ├── clickup.py              # HMAC-verified ClickUp webhook
│   │   └── callbacks.py            # GitHub Actions result callbacks
│   └── jobs/
│       ├── codebase_scan.py        # Weekly autonomous codebase audit
│       ├── weekly_summary.py       # Monday Slack digest
│       └── pattern_extraction.py   # Extract patterns from outcomes
├── .github/workflows/              # The pipeline — copy to your repo
│   ├── agent-triage.yml            # Issue triage → clarify or dispatch
│   ├── agent-write.yml             # Claude writes code → draft PR
│   ├── agent-review.yml            # Risk gate + review + spec audit
│   ├── agent-remediation.yml       # Auto-fix loop (max 2 rounds)
│   └── pattern-extraction.yml      # Weekly pattern extraction → rules PR
├── .claude/
│   ├── settings.json               # Hook configuration
│   ├── hooks/                      # Hard gates (safety, linting, tests)
│   └── rules/                      # Learned patterns (auto-generated)
│       ├── patterns.md             # What works well
│       └── anti-patterns.md        # Common mistakes to avoid
├── data/
│   └── agent-outcomes.jsonl        # Append-only log of every pipeline run
├── scripts/
│   ├── risk_policy_gate.py         # Determines risk tier from changed files
│   └── extract_patterns.py         # CLI wrapper for pattern extraction
├── risk-policy.json                # Risk tier rules — edit for your repo
├── ARCHITECTURE.md                 # Template — customize for your codebase
└── CLAUDE.md                       # Template — customize with your patterns
```

The orchestrator is **stateless**. GitHub Actions is the source of truth. The orchestrator's only job: receive events, route them, send notifications.

---

## Configuration

### risk-policy.json

Controls which file paths require which level of review:

```json
{
  "riskTierRules": {
    "high": ["app/auth/**", "**/*.sql", "app/admin/**"],
    "medium": ["app/routers/**", "app/services/**"],
    "low": ["docs/**", "*.md", "app/frontend/**"]
  },
  "mergePolicy": {
    "high":   {"requiredChecks": ["risk-policy-gate", "tests", "claude-review"]},
    "medium": {"requiredChecks": ["risk-policy-gate", "tests", "claude-review"]},
    "low":    {"requiredChecks": ["risk-policy-gate"]}
  }
}
```

### CLAUDE.md

The most important file. This is the agent's behavioral harness — it defines your codebase's patterns, invariants, and anti-patterns. Agents read this at the start of every session.

Key sections to customize:
- **Layer boundaries** — what depends on what
- **Architectural invariants** — what is *never* allowed
- **Patterns** — the right way to do auth, database access, etc.
- **Anti-patterns** — common mistakes to watch for

Keep it under 150 lines. Every line burns context tokens on every agent turn.

### .claude/hooks/

Hard gates that run *inside* the agent loop. The agent cannot reason around them:

| Hook | Trigger | Purpose |
|------|---------|---------|
| `inject-env.sh` | SessionStart | Inject DATABASE_URL, NEO4J_URI, etc. |
| `enforce-tenant-safety.sh` | PreToolUse(Bash) | Block DROP TABLE, unscoped DB writes |
| `run-linter.sh` | PostToolUse(Edit/Write) | Run ruff + mypy on changed files |
| `require-tests-pass.sh` | Stop | Prevent agent from stopping if tests fail |

---

## Self-Improving Pipeline

AgentFactory gets better over time through a closed feedback loop:

```
  Ticket → PR → Review → Outcome logged
                              │
                              ▼
                    Weekly pattern extraction
                              │
                              ▼
                    .claude/rules/ updated (via PR)
                              │
                              ▼
                    Next agent run reads learned patterns
```

1. **Outcome logging** — Every pipeline run is recorded in `data/agent-outcomes.jsonl` with the result, risk tier, files changed, review findings, cost, and duration.

2. **Pattern extraction** — A weekly job analyzes outcomes and proposes updates to `.claude/rules/`. Patterns require 3+ successful appearances; anti-patterns require 2+ recurring failures. Updates are submitted as PRs for human review.

3. **Agent reads rules** — Before writing code, the agent reads the latest learned patterns and anti-patterns. It learns from its own history across all tickets.

4. **Cost tracking** — Every PR body includes a stats table with cost, turns, and duration per step.

The separation is intentional: **`CLAUDE.md`** is the constitution (human-authored, never auto-modified). **`.claude/rules/`** is curated from data (auto-generated, human-reviewed before merge).

---

## Trigger Sources

| Source | Trigger | Orchestrator needed? | Setup complexity |
|--------|---------|---------------------|-----------------|
| **GitHub Issues** | Add `ai-agent` label | No | Workflow files + 3 secrets |
| **ClickUp** | Add `ai-agent` tag | Yes | Deploy orchestrator + webhook |
| **Manual dispatch** | `gh api repos/.../dispatches` | No | Workflow files + 3 secrets |

All sources produce the same `repository_dispatch` event. The downstream pipeline (write &rarr; review &rarr; remediate) is identical regardless of trigger source.

---

## Dogfooding

AgentFactory builds itself. This repo's own issues go through the same pipeline:

1. Create an issue describing a bug or feature
2. Add the `ai-agent` label
3. AgentFactory triages, writes code, opens a PR, reviews, and remediates
4. A human reviews and merges

This is the fastest way to understand what AgentFactory does — watch it work on its own codebase.

---

## Self-Hosting vs Managed

**Self-hosting (this repo):** Full control. Deploy to Cloud Run, configure your own GitHub App, bring your own API keys. Free beyond compute costs (~$0.10-0.50/PR in AI costs depending on complexity).

**Managed (coming soon):** One-click GitHub App install, hosted infrastructure, dashboard with cost analytics and success rates. [agentfactory.dev](https://agentfactory.dev)

---

## Contributing

PRs welcome. The codebase is ~2,100 lines of Python with 528 tests at 91% coverage. Key contribution areas:

- Additional webhook providers (Linear, Jira, Shortcut)
- Hook examples for common frameworks (Django, Rails, Express)
- Neon Database branching integration for per-run Postgres isolation
- E2B sandbox integration for higher-isolation agent runs
- MCP server integrations for database schema introspection

---

## License

MIT &mdash; see [LICENSE](LICENSE).
