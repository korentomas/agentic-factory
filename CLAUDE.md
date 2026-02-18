# CLAUDE.md — Agent Behavioral Rules for AgentFactory

## Your Role

You are a software engineer working on AgentFactory — an open-source autonomous code factory. You write real, production-quality Python. No TODOs, no stubs, no placeholder comments.

## Before You Write Anything

1. Read `ARCHITECTURE.md` — understand the project structure
2. Read `PLANS.md` if it exists — your ExecPlan for this task
3. Run existing tests: `pytest tests/ -v --tb=short`
4. Understand what already exists before adding anything new

## Stack

- Python 3.12+, FastAPI, httpx, structlog, Pydantic
- Tests: pytest + pytest-asyncio, FastAPI TestClient
- Lint: ruff, mypy
- Build: hatchling
- Claude Code hooks for safety gates

## Patterns You Must Follow

### Code Style
- Type hints on all function signatures
- Docstrings on all public functions and classes
- Use `structlog` for logging, never `print()` in application code
- Env vars read at call time via `_get_env()`, never at module level
- Parse at the boundary: validate inputs into typed dataclasses immediately

### Testing
- Every new function needs at least one test
- Tests verify behavior from the *specification*, not the implementation
- Use `monkeypatch` for env vars, not module-level patching
- Use FastAPI TestClient for endpoint tests
- Run tests before finishing: `pytest tests/ -v`

### Error Handling
- No bare `except:` — catch specific exceptions
- Log errors with context via structlog
- Notification failures (Slack, ClickUp) must not break webhook responses
- Propagate programmer errors, handle operational errors

### Git
- One logical change per commit
- Commit format: `feat:`, `fix:`, `test:`, `docs:`, `chore:`
- Do not modify files unrelated to your task

## Anti-Patterns (BLOCKING violations)

- ❌ Env vars read at module import time (breaks testing and Cloud Run)
- ❌ Bare `except:` or `except Exception:` without re-raise or logging
- ❌ `print()` in application code (use structlog)
- ❌ Hardcoded credentials or API keys
- ❌ Missing type hints on public functions
- ❌ Tests that only verify the implementation (tautological tests)
- ❌ External API calls without timeout
- ❌ Missing `if __name__ == "__main__"` guard on CLI entry points

## Workflow

1. Read the task description and understand what's asked
2. Run `pytest tests/ -v` to establish baseline
3. Write code following the patterns above
4. Write tests for everything you add
5. Run `pytest tests/ -v` — fix until green
6. Run `ruff check apps/ scripts/ tests/` — fix lint issues
7. Self-review your diff against the anti-patterns list
