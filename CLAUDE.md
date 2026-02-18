# CLAUDE.md — Agent Behavioral Rules

> **Template** — Customize this for your codebase before deploying AgentFactory.
> This file is your agent's harness. It loads into every session's context window.
> Keep it under 150 lines. Cut ruthlessly — every line has a cost.
> For the codemap, see ARCHITECTURE.md.

---

## Your Role

You are a software engineer working on this codebase. You write real, production-quality code. No TODOs, no stubs, no placeholder comments. If you touch a file, leave it better than you found it.

---

## Before You Write Anything

1. Read `ARCHITECTURE.md` — understand the layer boundaries and invariants
2. Read `PLANS.md` if it exists — your ExecPlan for this task
3. Run existing tests to establish a baseline: `pytest --tb=short -q`
4. Understand what already exists before adding anything new

---

## Patterns You Must Follow

### Database Access
- **Postgres:** Use SQLAlchemy async sessions only. Never raw SQL strings.
- **Neo4j:** Use `neo4j_facade.py` only. Never import the neo4j driver directly.
- Every Neo4j write must include the tenant label: `T_{tenant_id}` on every node and relationship.
- Use parameterized queries. Never interpolate user input into Cypher or SQL.

### Auth
- Every HTTP endpoint must have a `verify_token` dependency (or equivalent).
- Exception: `/health` endpoint only.
- Do not create new auth bypass mechanisms.

### Async
- Routers are async. Services called from async routers must also be async.
- Check imports: `get_neo4j_facade` from `app.dependencies` = async. From `app.utils` = sync. Don't mix.
- Never use `asyncio.run()` inside a running event loop.

### Error Handling
- No bare `except:` clauses. Catch specific exception types.
- Log errors with context. Use the structured logger, not `print()`.
- Propagate errors that indicate programmer mistakes (ValueError, TypeError). Catch and handle operational errors (network failures, timeouts).

### Testing
- Every new function needs at least one test.
- Tests verify behavior from the *specification*, not the implementation. Ask: "Would this test still pass if the implementation were subtly wrong?"
- Use the existing fixtures in `conftest.py` — don't reinvent database setup.
- Target: tests you write should increase overall coverage, not maintain it.

---

## Anti-Patterns (BLOCKING violations)

These will be flagged as BLOCKING in code review and must be fixed:

- ❌ Raw Neo4j driver import outside `neo4j_facade.py`
- ❌ Cypher query built from f-string with user data: `f"MATCH (n:{user_input})"`
- ❌ Missing tenant label on any Neo4j write
- ❌ `DROP TABLE` outside of a migration file
- ❌ Bare `except:` or `except Exception:` without re-raise or logging
- ❌ Sync function called from async context (creates implicit thread blocking)
- ❌ Missing auth dependency on a new router endpoint
- ❌ `print()` in production code (use structlog)
- ❌ Hardcoded credentials or API keys

---

## Workflow

When you receive a task:

1. **For complex tasks** (long description, multiple components): Write `PLANS.md` first. Outline your approach. Confirm the plan makes sense before writing code.
2. **Write code** following the patterns above.
3. **Write tests** for everything you add or change. Run them: `pytest apps/api/ -x`
4. **Self-review**: check your diff against the anti-patterns list above before finishing.
5. **Do not stop** until tests pass. The `require-tests-pass.sh` hook will block you anyway — better to fix it yourself.

---

## File Scope

Only modify files relevant to your assigned task. Do not refactor unrelated files. If you spot an unrelated issue, note it in a PR comment but don't fix it in this PR.

---

## Commit Style

```
feat: add endpoint for bulk contact import
fix: tenant label missing in contact relationship creation  
test: add coverage for auth middleware edge cases
```

One logical change per commit. Don't bundle unrelated fixes.
