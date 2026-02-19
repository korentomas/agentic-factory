<p align="center">
  <h1 align="center">LailaTov</h1>
  <p align="center">
    <strong>Your codebase, working while you sleep.</strong>
  </p>
  <p align="center">
    <a href="https://github.com/korentomas/agentic-factory/actions"><img src="https://github.com/korentomas/agentic-factory/actions/workflows/tests.yml/badge.svg" alt="Tests"></a>
    <a href="https://github.com/korentomas/agentic-factory/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
    <img src="https://img.shields.io/badge/python-3.12+-3776AB.svg?logo=python&logoColor=white" alt="Python 3.12+">
    <img src="https://img.shields.io/badge/next.js-15-black.svg?logo=next.js" alt="Next.js 15">
    <img src="https://img.shields.io/badge/Claude_Code-powered-cc785c.svg" alt="Claude Code">
  </p>
</p>

LailaTov ("good night" in Hebrew) is an autonomous code factory. Tag a GitHub issue, and it triages, writes code, opens a PR, reviews its own work, and fixes what the review flags. No human writes code. A human still reviews and merges.

It ships with a **web dashboard** (Next.js 15) for real-time task execution, an **agent runner** (FastAPI) with Docker sandbox isolation, and a **multi-engine architecture** supporting Claude Code, Codex, Aider, and any LiteLLM-compatible model.

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
├── apps/
│   ├── orchestrator/               # FastAPI service (Cloud Run)
│   │   ├── main.py                 # Webhook ingress, request ID middleware
│   │   ├── models.py               # AgentTask — parse at the boundary
│   │   ├── providers.py            # Multi-engine provider config
│   │   ├── routers/
│   │   │   ├── clickup.py          # HMAC-verified ClickUp webhook
│   │   │   └── callbacks.py        # GitHub Actions result callbacks
│   │   └── jobs/
│   │       ├── codebase_scan.py    # Weekly autonomous codebase audit
│   │       ├── weekly_summary.py   # Monday Slack digest
│   │       └── pattern_extraction.py
│   └── runner/                     # Agent execution service
│       ├── main.py                 # FastAPI — POST /tasks, GET /tasks/{id}
│       ├── engines/                # Multi-engine adapters
│       │   ├── protocol.py         # AgentEngine protocol
│       │   ├── claude_code.py      # Claude Code adapter
│       │   ├── aider.py            # Aider adapter (LiteLLM fallback)
│       │   ├── registry.py         # Engine selection logic
│       │   └── subprocess_util.py  # Cancel-aware subprocess runner
│       ├── sandbox.py              # Docker container isolation
│       ├── circuit_breaker.py      # Per-engine circuit breaker
│       ├── budget.py               # Per-task cost ceiling
│       ├── audit.py                # NDJSON event trail
│       ├── watchdog.py             # Overtime + zombie task detection
│       ├── github_tokens.py        # Short-lived GitHub App tokens
│       ├── litellm_proxy.py        # Unified model routing
│       ├── benchmark.py            # SWE-bench evaluation harness
│       ├── middleware.py            # Bearer token auth
│       └── workspace.py            # Git clone → branch → commit → push
├── web/                            # Next.js 15 dashboard
│   └── src/
│       ├── app/
│       │   ├── dashboard/          # Analytics dashboard
│       │   │   └── tasks/          # Open SWE-style task execution
│       │   │       └── [threadId]/ # Real-time streaming view
│       │   └── api/
│       │       ├── tasks/          # Task CRUD + SSE streaming
│       │       ├── chat/           # AI codebase assistant
│       │       └── stripe/         # Payments
│       ├── components/
│       │   ├── dashboard/          # Stats, PR table, engines, learning
│       │   └── tasks/              # Terminal input, progress bar, manager chat
│       └── lib/
│           ├── db/                 # Drizzle ORM + Postgres
│           ├── tasks/              # Task execution types
│           └── auth.ts             # NextAuth v5 + GitHub OAuth
├── .github/
│   ├── workflows/                  # The pipeline — copy to your repo
│   │   ├── agent-triage.yml
│   │   ├── agent-write.yml
│   │   ├── agent-review.yml
│   │   └── agent-remediation.yml
│   └── actions/run-agent/          # Multi-engine composite action
├── .claude/
│   ├── hooks/                      # Hard gates (safety, linting, tests)
│   └── rules/                      # Learned patterns (auto-generated)
├── data/
│   └── agent-outcomes.jsonl        # Append-only log of every pipeline run
└── risk-policy.json                # Risk tier rules — edit for your repo
```

The system has three layers: the **orchestrator** receives events and routes them, the **runner** executes agent tasks in sandboxed containers, and the **web dashboard** gives you real-time visibility into what the agents are doing.

---

## Task Execution UI

The web dashboard includes an **Open SWE-style task execution interface** (modeled after [langchain-ai/open-swe](https://github.com/langchain-ai/open-swe)):

- **Terminal input** — describe what you want built, select repo and branch
- **Real-time streaming** — SSE-powered view of agent execution with tool call rendering
- **Task progress bar** — segmented visualization of plan steps (completed/current/pending)
- **Manager chat** — interrupt and guide the agent mid-execution
- **Thread management** — list, revisit, and compare past task executions

Routes: `/dashboard/tasks` (thread list) and `/dashboard/tasks/[threadId]` (execution view).

---

## Agent Runner

The runner service (`apps/runner/`) executes coding agents as isolated subprocesses with production-grade safety:

| Feature | Description |
|---------|-------------|
| **Docker sandbox** | Each task runs in an isolated container with network allowlisting |
| **Circuit breaker** | Per-engine closed/open/half-open state machine prevents cascading failures |
| **Cost budget** | Per-task spending ceiling with automatic enforcement |
| **Task watchdog** | Background monitor detects overtime and zombie tasks |
| **GitHub App tokens** | Short-lived RS256 installation tokens, auto-refreshed |
| **Audit trail** | NDJSON-persistent event log for every lifecycle stage |
| **LiteLLM proxy** | Unified model routing with aliases and fallback chains |
| **Cancel support** | Graceful SIGTERM with 5-second SIGKILL escalation |

Multi-engine support: Claude Code, Aider (with any LiteLLM-compatible model), and extensible via the `AgentEngine` protocol.

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

PRs welcome. **987 backend tests** (96% coverage) + **266 frontend tests** across the monorepo.

Some things that would be useful:
- Webhook providers beyond ClickUp (Linear, Jira, Shortcut)
- Hook examples for Django, Rails, Express
- SWE-bench evaluation runs against the benchmark harness
- Additional engine adapters (Cursor, Windsurf, SWE-agent)
- MCP server integrations for database schema introspection

---

## License

MIT. See [LICENSE](LICENSE).
