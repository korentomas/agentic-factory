#!/usr/bin/env bash
# ── require-tests-pass.sh — Stop hook ────────────────────────────────────────
# Blocks the agent from stopping if tests fail.
# Exit code 2 = Claude Code blocks the Stop event and asks the agent to continue.
# Exit code 0 = tests pass, agent may stop.
# Exit code 1 = hook error (not a test failure) — agent may stop with warning.
#
# This is the primary quality gate inside the agent loop. The agent CANNOT
# declare itself done until this passes. It cannot be reasoned around.
set -euo pipefail

COVERAGE_FLOOR="${COVERAGE_FLOOR:-75}"
PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"

cd "$PROJECT_DIR"

# ── Detect test framework ──────────────────────────────────────────────────────
if [ -f "pyproject.toml" ] && grep -q "pytest" pyproject.toml 2>/dev/null; then
  TEST_CMD="pytest"
elif [ -f "package.json" ] && grep -q '"test"' package.json 2>/dev/null; then
  TEST_CMD="npm test"
else
  # No recognized test framework — let the agent stop (don't block)
  echo "No test framework detected in $(pwd) — skipping test gate" >&2
  exit 0
fi

# ── Run tests ──────────────────────────────────────────────────────────────────
echo "Running tests (coverage floor: ${COVERAGE_FLOOR}%)..." >&2

if [ "$TEST_CMD" = "pytest" ]; then
  # Find the main app directory
  if [ -d "apps" ]; then
    TEST_PATH="apps/"
  elif [ -d "app" ]; then
    TEST_PATH="app/"
  elif [ -d "src" ]; then
    TEST_PATH="src/"
  else
    TEST_PATH="."
  fi

  # Run with coverage. Output goes to stderr so Claude sees it.
  pytest "$TEST_PATH" \
    --cov="$TEST_PATH" \
    --cov-fail-under="$COVERAGE_FLOOR" \
    --tb=short \
    -q \
    2>&1 >&2
  EXIT_CODE=$?
else
  $TEST_CMD 2>&1 >&2
  EXIT_CODE=$?
fi

# ── Interpret result ───────────────────────────────────────────────────────────
if [ $EXIT_CODE -ne 0 ]; then
  echo "" >&2
  echo "┌─────────────────────────────────────────────────────────────────┐" >&2
  echo "│  STOP BLOCKED: Tests failed or coverage below ${COVERAGE_FLOOR}%            │" >&2
  echo "│                                                                 │" >&2
  echo "│  Fix the failures above before finishing. Do not declare done. │" >&2
  echo "└─────────────────────────────────────────────────────────────────┘" >&2
  # Exit 2 = Claude Code blocks the Stop event
  exit 2
fi

echo "✓ Tests pass (coverage ≥ ${COVERAGE_FLOOR}%) — agent may stop" >&2
exit 0
