# Architecture

## Bird's Eye

AgentFactory is an autonomous code factory. ClickUp tickets or GitHub Issues tagged `ai-agent` become reviewed, tested PRs via GitHub Actions + Claude Code.

Two parts: (1) a FastAPI orchestrator for ClickUp webhook → GitHub dispatch routing, and (2) GitHub Actions workflows that run Claude Code agents.

## Codemap

```
apps/orchestrator/
├── main.py                    FastAPI app — lifespan, middleware, health
├── models.py                  AgentTask dataclass — parse-at-boundary
├── routers/
│   ├── clickup.py             ClickUp webhook — HMAC verify, dispatch to GitHub
│   └── callbacks.py           GitHub Actions callbacks — notify Slack/ClickUp
└── jobs/
    ├── codebase_scan.py       Weekly scanner — Claude agent + ClickUp ticket creator
    └── weekly_summary.py      Monday digest — stats gatherer + Claude narrator

scripts/
└── risk_policy_gate.py        Risk tier calculator — glob matching, GH Actions output

.github/workflows/
├── agent-issue-trigger.yml    GitHub Issue → repository_dispatch
├── agent-write.yml            Claude writes code, creates draft PR
├── agent-review.yml           Risk gate → tests → Claude review → spec audit
├── agent-remediation.yml      Auto-fix loop (max 2 rounds)
└── test.yml                   CI — lint, type check, tests

.claude/
├── settings.json              Hook configuration (committed to repo)
└── hooks/                     Bash hooks: env inject, tenant safety, linter, test gate
```

## Architectural Invariants

- Env vars are NEVER read at module level. Always use `_get_env()` at call time.
- External API failures in notifications NEVER break webhook responses.
- Orchestrator callbacks are OPTIONAL — workflows work without orchestrator.
- All httpx calls have explicit timeouts.
- The orchestrator is STATELESS — GitHub is source of truth for agent runs.
- Parse at the boundary: webhook payloads → AgentTask dataclass immediately.

## Layer Boundaries

```
ClickUp Webhook / GitHub Issue
    │
    ▼
[routers/clickup.py]  ← HMAC verification, parse to AgentTask
    │
    ▼
[GitHub API]  ← repository_dispatch to target repo
    │
    ▼
[agent-write.yml]  ← Claude Code writes code
    │
    ▼
[agent-review.yml]  ← risk gate → tests → Claude review → spec audit
    │
    ├──▶ [agent-remediation.yml]  ← auto-fix (max 2 rounds)
    └──▶ [callbacks.py]  ← notify Slack + ClickUp
```
