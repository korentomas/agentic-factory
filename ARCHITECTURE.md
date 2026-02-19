# Architecture

## Bird's Eye

LailaTov (formerly AgentFactory) is an autonomous code factory. ClickUp tickets or GitHub Issues tagged `ai-agent` become reviewed, tested PRs via a multi-engine agent pipeline.

Three parts: (1) a FastAPI orchestrator for webhook → dispatch routing, (2) an Agent Runner service for executing coding agents as subprocesses, and (3) a Next.js website for customer-facing SaaS with Stripe payments.

Three layers: TRIAGE (evaluate clarity) → EXECUTE (write + review + remediate) → LEARN (extract patterns from outcomes).

## Codemap

```
apps/orchestrator/
├── main.py                    FastAPI app — lifespan, middleware, health, /ready
├── models.py                  AgentTask dataclass — parse-at-boundary
├── metrics.py                 Prometheus counters/histograms — custom registry
├── providers.py               Multi-provider config, engine selection, model tiering
├── runner_client.py           RunnerClient — HTTP bridge to Agent Runner service
├── routers/
│   ├── clickup.py             ClickUp webhook — HMAC verify, dispatch to GitHub
│   └── callbacks.py           GitHub Actions callbacks — notify Slack/ClickUp
└── jobs/
    ├── codebase_scan.py       Weekly scanner — Claude agent + ClickUp ticket creator
    ├── weekly_summary.py      Monday digest — stats gatherer + Claude narrator
    └── pattern_extraction.py  Outcome analyzer — extract patterns, update rules

apps/runner/                   Agent Runner — executes coding agents as subprocesses
├── main.py                    FastAPI service — POST /tasks, GET /tasks/{id}, cancel
├── models.py                  RunnerTask, RunnerResult, TaskState — domain types
├── workspace.py               Git workspace management — clone, branch, commit, push
└── engines/
    ├── protocol.py            AgentEngine protocol — interface for all adapters
    ├── registry.py            Engine selection — model → best engine mapping
    ├── subprocess_util.py     Shared async subprocess runner with timeout
    ├── claude_code.py         Claude Code adapter — wraps `claude --print`
    └── aider.py               Aider adapter — universal fallback via LiteLLM

web/                           Next.js website — customer-facing SaaS
├── src/app/                   App router pages (landing, login, dashboard, API routes)
├── src/components/            Bento grid, nav, pricing cards, footer
├── src/lib/                   Auth (NextAuth + GitHub), Stripe, utilities
└── .env.example               Required env vars for local dev

.github/
├── actions/run-agent/         Composite action — dispatches to any engine
│   └── action.yml             Inputs: engine, model, prompt → normalized outputs
└── workflows/
    ├── agent-triage.yml       Issue triage → clarify or dispatch
    ├── agent-write.yml        Agent writes code, creates draft PR
    ├── agent-review.yml       Risk gate → tests → review → spec audit → outcome log
    ├── agent-remediation.yml  Auto-fix loop (max 2 rounds, then escalation)
    ├── pattern-extraction.yml Weekly pattern extraction → rules PR
    └── test.yml               CI — lint, type check, tests

scripts/
└── risk_policy_gate.py        Risk tier calculator — glob matching, GH Actions output

data/
└── agent-outcomes.jsonl       Structured log of every pipeline run (JSONL)

docs/
├── providers.md               Multi-provider configuration guide
├── engines.md                 Engine-specific setup (claude-code, codex, gemini-cli)
└── research/                  Business and design research
    ├── cost-analysis.md       LLM pricing, COGS, tier structure
    └── design-philosophy.md   Japanese aesthetics, color palette, design tokens

.claude/
├── settings.json              Hook configuration (committed to repo)
├── hooks/                     Bash hooks: env inject, tenant safety, linter, test gate
└── rules/                     Learned patterns (auto-generated, human-reviewed)
    ├── patterns.md            What works well across PRs
    └── anti-patterns.md       Common mistakes to avoid
```

## Architectural Invariants

- Env vars are NEVER read at module level. Always use `_get_env()` at call time.
- External API failures in notifications NEVER break webhook responses.
- Orchestrator callbacks are OPTIONAL — workflows work without orchestrator.
- All httpx calls have explicit timeouts.
- The orchestrator is STATELESS — GitHub is source of truth for agent runs.
- Parse at the boundary: webhook payloads → AgentTask dataclass immediately.
- CLAUDE.md is the constitution (human-authored, never auto-modified).
- `.claude/rules/` is curated from data (auto-generated, human-reviewed before merge).
- Outcome data (`agent-outcomes.jsonl`) is append-only.
- Engine adapters use `create_subprocess_exec` (not shell) — no injection risk.
- The Agent Runner owns workspace lifecycle: create → execute → commit → cleanup.

## Dispatch Paths

Two dispatch paths exist — the orchestrator chooses based on `DISPATCH_TARGET`:

1. **GitHub Actions** (default): Orchestrator → `repository_dispatch` → workflow YAML
2. **Agent Runner**: Orchestrator → `RunnerClient` → Runner HTTP API → subprocess

The Runner path gives full control over workspace lifecycle, engine selection,
and cost tracking without CI limitations (6h timeout, cold starts, no state).

## Layer Boundaries

```
ClickUp Webhook / GitHub Issue (labeled "ai-agent")
    │
    ▼
[agent-triage.yml]  ← Claude evaluates clarity
    │
    ├──▶ CLEAR → dispatch to agent-write
    └──▶ UNCLEAR → post clarification question, wait for reply
    │
    ▼
[agent-write.yml]  ← Claude Code writes code + creates draft PR
    │                  Reads: CLAUDE.md, ARCHITECTURE.md, .claude/rules/
    │                  Captures: cost, turns, duration
    ▼
[agent-review.yml]  ← risk gate → tests → Claude review → spec audit
    │                   Logs outcome to data/agent-outcomes.jsonl
    │                   Auto-promotes clean PRs from draft to ready
    │
    ├──▶ CLEAN → PR marked ready for review
    ├──▶ BLOCKING → [agent-remediation.yml] (max 2 rounds)
    └──▶ ESCALATE → Slack notification + PR comment
    │
    ▼
[pattern-extraction.yml]  ← Weekly: analyze outcomes → propose rules updates
    │
    └──▶ PR to update .claude/rules/ (human-reviewed before merge)
```
