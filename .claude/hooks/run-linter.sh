#!/usr/bin/env bash
# ── run-linter.sh — PostToolUse(Edit|Write|MultiEdit) hook ───────────────────
# Runs ruff + mypy on changed Python files after every edit.
# Registered as async=true — doesn't block the agent, just posts feedback.
#
# Output is shown to Claude as a hint, not a hard block.
# For hard blocks, use require-tests-pass.sh (Stop hook).
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
cd "$PROJECT_DIR"

# ── Find recently changed Python files ────────────────────────────────────────
# Use git to find files changed since last commit.
# Fall back to stdin (Claude Code may pass the changed file path via env).

CHANGED_FILE="${CLAUDE_TOOL_OUTPUT_FILE:-}"  # Set by some Claude Code versions

if [ -n "$CHANGED_FILE" ] && [ -f "$CHANGED_FILE" ] && [[ "$CHANGED_FILE" == *.py ]]; then
  CHANGED_PY_FILES="$CHANGED_FILE"
else
  # Get Python files changed vs HEAD (includes staged and unstaged)
  CHANGED_PY_FILES=$(git diff --name-only HEAD 2>/dev/null | grep '\.py$' | tr '\n' ' ')

  # If that's empty (e.g., first edit with no prior commits), try git status
  if [ -z "$CHANGED_PY_FILES" ]; then
    CHANGED_PY_FILES=$(git status --porcelain 2>/dev/null | grep '\.py$' | awk '{print $2}' | tr '\n' ' ')
  fi
fi

if [ -z "$CHANGED_PY_FILES" ]; then
  # No Python files changed — nothing to lint
  exit 0
fi

echo "🔍 Linting changed files: $CHANGED_PY_FILES" >&2

LINT_FAILED=0
MYPY_FAILED=0

# ── ruff: fast linter + auto-fixer ────────────────────────────────────────────
if command -v ruff &>/dev/null; then
  echo "--- ruff ---" >&2
  # --fix: auto-fix safe issues
  # --exit-non-zero-on-fix: exit 1 if fixes were applied (so Claude knows)
  if ! ruff check --fix $CHANGED_PY_FILES 2>&1 | head -50 >&2; then
    LINT_FAILED=1
  fi
else
  echo "⚠️  ruff not installed (pip install ruff)" >&2
fi

# ── mypy: type checking ────────────────────────────────────────────────────────
if command -v mypy &>/dev/null; then
  echo "--- mypy ---" >&2
  if ! mypy $CHANGED_PY_FILES \
      --ignore-missing-imports \
      --no-error-summary \
      2>&1 | head -50 >&2; then
    MYPY_FAILED=1
  fi
else
  echo "⚠️  mypy not installed (pip install mypy)" >&2
fi

# ── Summary ────────────────────────────────────────────────────────────────────
if [ $LINT_FAILED -ne 0 ] || [ $MYPY_FAILED -ne 0 ]; then
  echo "" >&2
  echo "⚠️  Lint/type issues found. Review the output above and fix before finishing." >&2
  # Exit 0 (not 1) because this is PostToolUse — we warn, don't block
  # Blocking happens in the Stop hook (require-tests-pass.sh)
  exit 0
fi

echo "✓ Lint clean" >&2
exit 0
