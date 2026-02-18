# AgentFactory

**Your tickets become PRs. Automatically.**

AgentFactory is an open-source autonomous code factory that takes ClickUp tickets tagged `ai-agent` and turns them into reviewed, tested pull requests — without a human writing a single line of code. It's like CodeRabbit, but it *writes* the code, not just comments on it.

Drop a ticket. Come back to a PR.

---

## How It Works

```
  You add tag "ai-agent" to a ClickUp ticket
              │
              ▼
  ┌─────────────────────────┐
  │  Agent Orchestrator     │  Cloud Run — receives webhook,
  │  (this repo)            │  parses ticket, fires GitHub dispatch
  └────────────┬────────────┘
               │  POST /repos/.../dispatches
               ▼
  ┌─────────────────────────┐
  │  agent-write.yml        │  GitHub Actions — Claude Sonnet writes
  │  (target repo)          │  code, creates draft PR, posts callback
  └────────────┬────────────┘
               │  PR opened on branch agent/*
               ▼
  ┌─────────────────────────┐
  │  agent-review.yml       │  Risk gate → tests → Claude Opus review
  │  (target repo)          │  + spec coverage audit
  └────────────┬────────────┘
               │
      ┌────────┴────────┐
      │                 │
   FINDINGS           CLEAN
      │                 │
      ▼                 ▼
  agent-             Orchestrator posts
  remediation        ClickUp comment +
  .yml               Slack notification
  (max 2 rounds,
   then escalate)
```

---

## Quickstart

**1. Clone and configure**

```bash
git clone https://github.com/your-org/agent-factory
cd agent-factory
cp .env.example .env
# Fill in: CLICKUP_WEBHOOK_SECRET, GITHUB_APP_TOKEN, CLICKUP_API_TOKEN, SLACK_WEBHOOK_URL
```

**2. Copy workflow files to your target repo**

```bash
cp .github/workflows/*.yml /path/to/your-repo/.github/workflows/
cp .claude/settings.json /path/to/your-repo/.claude/
cp -r .claude/hooks/ /path/to/your-repo/.claude/
cp risk-policy.json /path/to/your-repo/
cp ARCHITECTURE.md /path/to/your-repo/
cp CLAUDE.md /path/to/your-repo/
```

**3. Set GitHub Actions secrets in your target repo**

```
ANTHROPIC_API_KEY    — Your Anthropic API key
GITHUB_APP_TOKEN     — GitHub App token (must use App, not GITHUB_TOKEN)
ORCHESTRATOR_URL     — URL of your deployed orchestrator, e.g. https://agent-factory.run.app
CLICKUP_API_TOKEN    — ClickUp personal API token
SLACK_WEBHOOK_URL    — Slack incoming webhook URL
```

**4. Deploy the orchestrator**

```bash
# Using Cloud Run
gcloud run deploy agent-factory \
  --source . \
  --region us-central1 \
  --set-env-vars-from-file .env

# Or locally for testing
pip install -e .
uvicorn apps.orchestrator.main:app --port 8080
```

**5. Register the ClickUp webhook**

```bash
curl -X POST https://api.clickup.com/api/v2/team/YOUR_TEAM_ID/webhook \
  -H "Authorization: YOUR_CLICKUP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://YOUR_ORCHESTRATOR_URL/webhooks/clickup",
    "events": ["taskTagUpdated"]
  }'
```

Now tag any ClickUp ticket with `ai-agent` and watch it become a PR.

---

## Architecture Overview

```
agent-factory/
├── apps/orchestrator/       # FastAPI service (Cloud Run)
│   ├── main.py              # Webhook ingress + routing
│   ├── models.py            # AgentTask — parse-at-boundary
│   ├── routers/
│   │   ├── clickup.py       # HMAC-verified ClickUp webhook
│   │   └── callbacks.py     # GitHub Actions result callbacks
│   └── jobs/
│       ├── codebase_scan.py # Weekly autonomous codebase audit
│       └── weekly_summary.py# Monday Slack digest
├── .github/workflows/       # Copy these to your target repo
│   ├── agent-write.yml      # Claude writes code → draft PR
│   ├── agent-review.yml     # Risk gate + review + spec audit
│   └── agent-remediation.yml# Auto-fix loop (max 2 rounds)
├── .claude/                 # Copy to your target repo
│   ├── settings.json        # Hook configuration
│   └── hooks/               # Bash hooks (safety, linting, tests)
├── scripts/
│   └── risk_policy_gate.py  # Determines risk tier from changed files
├── risk-policy.json         # Risk tier rules — edit for your repo
├── ARCHITECTURE.md          # Template — customize for your codebase
└── CLAUDE.md                # Template — customize with your patterns
```

The orchestrator is stateless. GitHub Actions is the source of truth for agent runs. The orchestrator's only job: receive events, route them, send notifications.

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

High-tier PRs require passing tests AND Claude review. Low-tier only need the gate.

### CLAUDE.md

The most important file. This is the agent's harness — it defines your codebase's patterns, invariants, and what NOT to do. Agents read this at the start of every session.

Key sections to customize:
- **Layer boundaries** — what depends on what
- **Architectural invariants** — what is *never* allowed (explicit absences)
- **Patterns** — the right way to do auth, database access, etc.
- **Anti-patterns** — common mistakes to avoid

Keep it under 150 lines. Every line burns context tokens on every agent turn.

### .claude/hooks/

Hard gates that run *inside* the agent loop and cannot be reasoned around:

| Hook | Trigger | What it does |
|------|---------|-------------|
| `inject-env.sh` | SessionStart | Sets DATABASE_URL, NEO4J_URI, etc. |
| `enforce-tenant-safety.sh` | PreToolUse(Bash) | Blocks DROP TABLE, raw DB writes without tenant scope |
| `run-linter.sh` | PostToolUse(Edit/Write) | Runs ruff + mypy on changed files (async) |
| `require-tests-pass.sh` | Stop | Prevents agent from stopping if tests fail (exit 2) |

---

## Self-Hosting vs Managed

**Self-hosting (this repo):** Full control. Deploy the orchestrator to Cloud Run, configure your own GitHub App, bring your own secrets. Free beyond compute costs (~$0.10–0.50/PR in AI costs).

**Managed (coming soon):** One-click install, no infra to manage. Sign up at [agentfactory.dev](https://agentfactory.dev) *(waitlist open)*.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contributing

PRs welcome. The codebase is intentionally small (~400 lines of Python). Key contribution areas:

- Additional webhook providers (Linear, Jira, GitHub Issues)
- More hook examples for common frameworks (Django, Rails, Express)
- Neon Database branching integration for per-run Postgres isolation
- E2B sandbox integration for higher-isolation agent runs
# agentic-factory
