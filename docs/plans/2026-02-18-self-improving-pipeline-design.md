# Self-Improving Pipeline Design

**Date**: 2026-02-18
**Status**: Draft — awaiting discussion

---

## Problem Statement

AgentFactory currently operates as a stateless pipeline: issue in, PR out. It has no memory of past runs, no ability to ask clarifying questions, and no mechanism to improve over time. Every ticket starts from scratch with only CLAUDE.md as guidance.

## Vision

An agent that gets better at writing code for YOUR codebase with every ticket it resolves. It remembers what patterns work, what review findings it keeps getting, and knows when to ask before guessing.

---

## Architecture: Three Layers

```
Layer 1: TRIAGE (before coding)
  "Is this issue clear enough to implement?"
  → Ask clarifying questions, estimate complexity, check for duplicates

Layer 2: EXECUTE (current pipeline, enhanced)
  "Write, review, remediate"
  → Now with cost tracking, auto-promotion, and MCP-powered DB access

Layer 3: LEARN (after merge/reject)
  "What worked? What didn't?"
  → Record outcomes, extract patterns, improve future runs
```

---

## Phase 1: Issue Triage + Clarification

**New workflow: `agent-triage.yml`**

Triggered: `issues.labeled` with `ai-agent` label (replaces current direct dispatch)

```
Issue labeled "ai-agent"
  │
  ▼
[Read issue + codebase context]
  │
  ├── Is the issue clear?
  │     YES → Post specification comment, dispatch to agent-write
  │     NO  → Post ONE clarifying question with default assumption
  │           Add label: "needs-clarification"
  │           Wait for author response
  │
  ▼
[Author responds]
  │
  ▼
[Re-evaluate, dispatch to agent-write with enriched context]
```

**Specification comment format** (inspired by Copilot Workspace):
```markdown
## Specification

### Current State
- `/health` endpoint returns `{"status": "ok", "service": "..."}`
- No version information exposed

### Desired State
- `/health` endpoint returns `{"status": "ok", "service": "...", "version": "0.1.0"}`
- Version sourced from `apps/__init__.py`

### Implementation Plan
1. Add `__version__` to `apps/__init__.py`
2. Import and include in health response
3. Update existing test

**Does this look right? Reply to confirm or suggest changes.**
**Auto-proceeding in 24h if no objection.**
```

**Key design decisions:**
- ONE question at a time, with a recommended default
- 24h timeout with auto-proceed (configurable)
- Spec posted as issue comment (not a separate artifact)
- Agent reads spec comment when writing code (not just raw issue body)

---

## Phase 2: Structured Outcome Logging (Foundation)

**Purpose**: Collect data before trying to learn from it.

After every pipeline completion (merge, reject, or abandon), record:

```json
{
  "task_id": "gh-1",
  "issue_url": "https://github.com/.../issues/1",
  "pr_url": "https://github.com/.../pull/2",
  "outcome": "merged",
  "files_changed": ["apps/__init__.py", "apps/orchestrator/main.py"],
  "cost_usd": 0.47,
  "turns_total": 23,
  "duration_s": 312,
  "review_findings": [],
  "remediation_rounds": 0,
  "risk_tier": "medium",
  "complexity": "high",
  "timestamp": "2026-02-18T22:00:00Z"
}
```

**Storage options** (in priority order):

| Option | Pros | Cons | When |
|--------|------|------|------|
| **JSON Lines file in repo** | Zero infra, git-versioned | No querying | Start here |
| **SQLite + MCP server** | Queryable, agent-accessible | Need MCP setup | Phase 3 |
| **Neo4j knowledge graph** | Rich relationships, cross-repo | Infrastructure | Phase 4+ |

**Implementation**: Append to `data/agent-outcomes.jsonl` after each pipeline run. Committed by the agent-write or notify-orchestrator step.

---

## Phase 3: Memory-Augmented Agent Runs

**Purpose**: Close the feedback loop — agent queries past outcomes while working.

### Filesystem Design

```
.claude/
  rules/                      # Checked into repo (team-shared)
    patterns.md               # High-confidence rules extracted from outcomes
    anti-patterns.md          # Common mistakes discovered from review findings
    # These are CURATED — human-reviewed before commit
    # Updated by weekly pattern-extraction job

data/
  agent-outcomes.jsonl        # Raw outcome log (append-only)
  learnings.db                # SQLite — queryable via MCP (gitignored)
```

**Key separation** (from research):
- **CLAUDE.md**: Constitution — rules that never drift. Human-authored.
- **`.claude/rules/*.md`**: Extracted patterns — curated from data, human-reviewed before merge.
- **`data/learnings.db`**: Runtime memory — agent queries via MCP, not committed.
- **Auto-memory (`~/.claude/projects/...`)**: Per-user, session-specific. Not used in CI.

### MCP Server for Agent Access

During agent-write runs, Claude Code can query the learnings DB:

```yaml
# In agent-write.yml, via CLAUDE_SETTINGS secret:
{
  "mcpServers": {
    "learnings": {
      "command": "npx",
      "args": ["sqlite-explorer-fastmcp", "--db", "data/learnings.db"]
    }
  }
}
```

Agent prompt addition:
```
Before writing code, check the learnings database for:
- Past issues similar to this one (query by file paths or keywords)
- Common review findings for this area of the codebase
- Patterns that worked well in previous PRs touching these files
```

### Weekly Pattern Extraction Job

New job in `apps/orchestrator/jobs/pattern_extraction.py`:

```python
def extract_patterns(outcomes: list[AgentOutcome]) -> list[Pattern]:
    """Analyze recent outcomes and extract reusable patterns.

    Rules:
    - A pattern must appear in 3+ successful PRs to be promoted
    - A review finding that appears 2+ times becomes an anti-pattern
    - Patterns are proposed as a PR to .claude/rules/, not auto-committed
    """
```

This runs weekly (like existing `codebase_scan.py`) and creates a PR with proposed rule updates. Humans review and merge.

---

## Phase 4: Database Access for Target Repos

**Purpose**: Let the agent understand the target repo's database schema.

### MCP Servers

| Database | MCP Server | Config |
|----------|-----------|--------|
| PostgreSQL | `postgres-mcp` (crystaldba) | Read-only role, SSE transport |
| Neo4j | `mcp-neo4j-cypher` | `NEO4J_READ_ONLY=true` |
| Redis | Custom or skip | Schema-less, less useful |
| SQLite | `sqlite-explorer-fastmcp` | Built-in read-only |

### Integration Pattern

Target repos add MCP config to their `.claude/settings.json`:

```json
{
  "mcpServers": {
    "project-db": {
      "command": "npx",
      "args": ["@crystaldba/postgres-mcp"],
      "env": {
        "DATABASE_URL": "postgresql://readonly:***@localhost:5432/app",
        "READONLY": "true"
      }
    }
  }
}
```

In CI, the service containers provide the databases. The MCP server runs alongside Claude Code and gives it schema introspection (tables, columns, relationships, indexes) without needing to read migration files.

### Managed Platform (Future)

For the managed version (agentfactory.dev):

1. User signs up, installs GitHub App
2. Onboarding wizard:
   - Connect repo
   - Connect databases (read-only credentials)
   - Configure AI provider (Anthropic / OpenRouter / Bedrock)
3. We generate `.claude/settings.json` with MCP servers pre-configured
4. We manage secrets via the GitHub App (encrypted, scoped)
5. Dashboard shows cost per ticket, success rate, common findings

---

## Roadmap Summary

| Phase | What | Effort | Dependencies |
|-------|------|--------|-------------|
| **1a** | Issue triage workflow | 1-2 days | None |
| **1b** | Clarification comment + wait | 1 day | 1a |
| **2** | Outcome logging (JSONL) | 0.5 day | None |
| **3a** | SQLite learnings DB + MCP | 1-2 days | Phase 2 |
| **3b** | Weekly pattern extraction job | 2-3 days | Phase 2 |
| **3c** | `.claude/rules/` auto-updates | 1 day | Phase 3b |
| **4** | DB MCP servers in CI | 1 day | None |
| **5** | Managed platform (website) | Weeks | All above |

**Progress** (as of 2026-02-18):
- [x] Auto-promote draft PRs (shipped, verified on PRs #5, #7, #8)
- [x] Cost tracking structure in PR body (NDJSON parsing, show_full_output)
- [x] Phase 1a: agent-triage.yml (shipped, tested with Issues #3, #4, #6)
- [x] Phase 1b: Clarification comments + wait-for-reply (shipped, tested on Issue #4)
- [x] Phase 2: Outcome logging — JSONL (shipped, 3 records logged)
- [x] Phase 3b: Pattern extraction job (shipped — `pattern_extraction.py` + 57 tests)
- [x] Phase 3c: `.claude/rules/` auto-updates via weekly workflow
- [x] Review findings capture in outcome log (GitHub API for bot comments)
- [x] Changed files tracking via GitHub PR files API
- [x] Concurrency groups on agent-write and agent-review
- [x] Remediation → Slack escalation + learned rules reading
- [x] CLI entry point for pattern extraction (`agentfactory-extract`)
- [ ] Phase 3a: SQLite learnings DB + MCP server (deferred — JSONL sufficient for now)
- [ ] Phase 4: DB MCP servers in CI
- [ ] Phase 5: Managed platform

**Verified end-to-end flows:**
1. Issue #3 (clear) → triage → dispatch → PR #5 → review (all pass) → auto-promote
2. Issue #4 (unclear) → triage → clarification → reply → re-triage → dispatch → PR #8 → review (all pass, high risk)
3. Issue #6 (clear) → triage → dispatch → PR #7 → review (all pass) → auto-promote
4. Pattern extraction runs correctly with 3 outcomes (100% success rate)
5. Outcome logging captures results after every review run
