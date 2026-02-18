# Architecture

## Bird's Eye

AgentFactory is an autonomous code factory. ClickUp tickets or GitHub Issues tagged `ai-agent` become reviewed, tested PRs via GitHub Actions + Claude Code.

Two parts: (1) a FastAPI orchestrator for ClickUp webhook → GitHub dispatch routing, and (2) GitHub Actions workflows that run Claude Code agents.

Three layers: TRIAGE (evaluate clarity) → EXECUTE (write + review + remediate) → LEARN (extract patterns from outcomes).

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
    ├── weekly_summary.py      Monday digest — stats gatherer + Claude narrator
    └── pattern_extraction.py  Outcome analyzer — extract patterns, update rules

scripts/
└── risk_policy_gate.py        Risk tier calculator — glob matching, GH Actions output

.github/workflows/
├── agent-triage.yml           Issue triage → clarify or dispatch
├── agent-write.yml            Claude writes code, creates draft PR (with cost tracking)
├── agent-review.yml           Risk gate → tests → Claude review → spec audit → outcome log
├── agent-remediation.yml      Auto-fix loop (max 2 rounds, then Slack escalation)
├── pattern-extraction.yml     Weekly pattern extraction → rules PR
└── test.yml                   CI — lint, type check, tests

data/
└── agent-outcomes.jsonl       Structured log of every pipeline run (JSONL, one record per line)

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
