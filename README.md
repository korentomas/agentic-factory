<p align="center">
  <h1 align="center">AgentFactory</h1>
  <p align="center">
    <strong>Tag a ticket. Get a PR.</strong>
  </p>
  <p align="center">
    <a href="https://github.com/korentomas/agentic-factory/actions"><img src="https://github.com/korentomas/agentic-factory/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
    <a href="https://github.com/korentomas/agentic-factory/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
    <img src="https://img.shields.io/badge/python-3.12+-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12+">
    <img src="https://img.shields.io/badge/Claude_Code-powered-cc785c.svg" alt="Claude Code">
  </p>
</p>

AgentFactory turns GitHub Issues and ClickUp tickets into reviewed, tested pull requests. Add the `ai-agent` label to an issue, and it figures out what to build, writes the code, opens a draft PR, runs the test suite, reviews its own work, fixes anything the review flags, and marks it ready. No human writes code. A human still reviews and merges.

It also keeps a log of every run and uses that data to get better at your codebase over time.

---

## How it works

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
                    agent-            for review
                    remediation.yml
                    (max 2 rounds,
                     then Slack
                     escalation)
```

The pipeline has three stages. **Triage** decides if the issue is clear enough to work on (if not, it posts a clarifying question and waits). **Write** generates the code and opens a draft PR. **Review** runs a risk gate, the test suite, a code review, and a spec audit. If the review finds problems, a remediation loop fixes them automatically, up to twice, then escalates to Slack.

Each run costs roughly $0.10-0.50 in API calls depending on complexity. Cost, turn count, and duration are printed in every PR body.

---

## Quickstart

### Option A: GitHub Issues (no infrastructure needed)

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

Create a [GitHub App](https://docs.github.com/en/apps/creating-github-apps) with Contents, Pull requests, and Issues permissions (Read & Write for each).

Install it on your target repo, then add these GitHub Actions secrets:

| Secret | Required | Description |
|--------|----------|-------------|
| `APP_ID` | Yes | Your GitHub App's ID |
| `APP_PRIVATE_KEY` | Yes | The app's private key (`.pem` contents) |
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key (or OpenRouter key) |
| `SLACK_WEBHOOK_URL` | No | Slack webhook for escalation notifications |

Workflows use [`actions/create-github-app-token`](https://github.com/actions/create-github-app-token) to generate short-lived tokens scoped to the installation, so you don't need a PAT.

**4. Create an issue and add the `ai-agent` label**

The pipeline takes it from there. No orchestrator, no webhooks, nothing else to deploy.

### Option B: ClickUp integration

This path requires deploying the orchestrator service.

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

The orchestrator dispatches to the same GitHub Actions pipeline used by Issues.

### Using OpenRouter or other providers

Add one more secret:

```
CLAUDE_SETTINGS = {"env":{"ANTHROPIC_BASE_URL":"https://openrouter.ai/api"}}
```

Set `ANTHROPIC_API_KEY` to your OpenRouter key (`sk-or-v1-...`). Works with any model OpenRouter supports.

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

The orchestrator is stateless. GitHub Actions is the source of truth for what happened. The orchestrator just receives events, routes them, and sends notifications.

---

## Configuration

### risk-policy.json

Maps file paths to risk tiers. High-risk PRs (auth, SQL, admin) get the full review pipeline. Low-risk PRs (docs, markdown) only need the gate check.

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

This is the most important file in the repo. It tells the agent how your codebase works: what patterns to follow, what invariants to respect, what to never do. The agent reads it at the start of every session.

Customize the layer boundaries, the do/don't lists, and the error handling rules for your project. Keep it under 150 lines. Every line costs context tokens on every turn.

### .claude/hooks/

Hard gates that run inside the agent loop. The agent can't talk its way around these:

| Hook | Trigger | What it does |
|------|---------|--------------|
| `inject-env.sh` | SessionStart | Injects DATABASE_URL, NEO4J_URI, etc. |
| `enforce-tenant-safety.sh` | PreToolUse(Bash) | Blocks DROP TABLE, unscoped DB writes |
| `run-linter.sh` | PostToolUse(Edit/Write) | Runs ruff + mypy on changed files |
| `require-tests-pass.sh` | Stop | Won't let the agent stop if tests fail |

---

## Self-improving pipeline

Every pipeline run is logged to `data/agent-outcomes.jsonl` with the result, risk tier, changed files, review findings, cost, and duration.

A weekly job reads the log and looks for patterns. If the same file-level pattern shows up in 3+ successful PRs, it gets promoted to `.claude/rules/patterns.md`. If a review finding recurs in 2+ failures, it becomes an anti-pattern. Either way, the update is submitted as a PR for a human to review before it goes live.

The next agent run reads those rules before writing code. So the agent learns from its own history, but a human still approves what it learns.

The split between `CLAUDE.md` and `.claude/rules/` is intentional. CLAUDE.md is human-authored and never auto-modified. The rules directory is generated from data and goes through PR review before merge.

---

## Trigger sources

| Source | Trigger | Orchestrator? | Setup |
|--------|---------|--------------|-------|
| GitHub Issues | Add `ai-agent` label | No | Workflow files + 3 secrets |
| ClickUp | Add `ai-agent` tag | Yes | Deploy orchestrator + webhook |
| Manual dispatch | `gh api repos/.../dispatches` | No | Workflow files + 3 secrets |

All three produce the same `repository_dispatch` event. The downstream pipeline is identical.

---

## Dogfooding

This repo uses AgentFactory on itself. Create an issue, add the `ai-agent` label, and watch the pipeline triage it, write the code, review it, and open a PR. You review and merge.

Probably the fastest way to see what it actually does.

---

## Self-hosting vs managed

**Self-hosting (this repo):** You deploy to Cloud Run, configure your own GitHub App, bring your own API keys. Free beyond compute and AI costs ($0.10-0.50/PR).

**Managed (coming soon):** One-click GitHub App install, hosted infra, cost dashboard. [agentfactory.dev](https://agentfactory.dev)

---

## Contributing

PRs welcome. ~2,100 lines of Python, 528 tests, 91% coverage.

Some things that would be useful:
- Webhook providers beyond ClickUp (Linear, Jira, Shortcut)
- Hook examples for Django, Rails, Express
- Neon Database branching for per-run Postgres isolation
- E2B sandbox integration for higher-isolation runs
- MCP server integrations for database schema introspection

---

## License

MIT. See [LICENSE](LICENSE).
