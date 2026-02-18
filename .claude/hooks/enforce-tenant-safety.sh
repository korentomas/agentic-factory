#!/usr/bin/env bash
# ── enforce-tenant-safety.sh — PreToolUse(Bash) hook ─────────────────────────
# Blocks destructive database operations and unscoped writes.
# This hook reads the Bash command Claude is about to run from stdin (JSON).
#
# Claude Code passes the tool input as JSON on stdin:
# { "command": "...", "description": "..." }
#
# Exit 0 = allow the command
# Exit 1 = block with error message (printed to stderr, shown to Claude)
set -euo pipefail

# Read the tool input JSON from stdin
INPUT=$(cat)

# Extract the command string (handle both "command" and "cmd" keys)
COMMAND=$(echo "$INPUT" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('command', data.get('cmd', '')))
" 2>/dev/null || echo "")

if [ -z "$COMMAND" ]; then
  # Can't parse input — allow through (don't block on parse errors)
  exit 0
fi

# ── Blocked patterns ──────────────────────────────────────────────────────────
# Each pattern has a message explaining WHY it's blocked and what to do instead.

# Postgres: destructive DDL
if echo "$COMMAND" | grep -qiE "DROP\s+TABLE|DROP\s+DATABASE|TRUNCATE\s+TABLE"; then
  echo "BLOCKED: Destructive DDL detected." >&2
  echo "  Command: $COMMAND" >&2
  echo "  Reason: DROP TABLE and TRUNCATE must be Alembic migrations, not inline SQL." >&2
  echo "  Fix: Create a migration file in apps/api/migrations/ instead." >&2
  exit 1
fi

# Postgres: unscoped bulk delete
if echo "$COMMAND" | grep -qiE "DELETE\s+FROM\s+\w+\s+WHERE\s+1\s*=\s*1"; then
  echo "BLOCKED: Unscoped bulk DELETE detected." >&2
  echo "  Command: $COMMAND" >&2
  echo "  Reason: This would delete all rows. Add a specific WHERE clause." >&2
  exit 1
fi

# Neo4j: DETACH DELETE without a tenant label
# Pattern: DETACH DELETE or DELETE on a node that doesn't have T_ label
if echo "$COMMAND" | grep -qiE "DETACH\s+DELETE|MATCH\s*\(.*\)\s*DELETE"; then
  # Allow if it has a tenant label pattern T_{something}
  if ! echo "$COMMAND" | grep -qE "T_\{?[a-zA-Z_][a-zA-Z0-9_]*\}?"; then
    echo "BLOCKED: Neo4j DELETE without tenant label." >&2
    echo "  Command: $COMMAND" >&2
    echo "  Reason: All Neo4j writes/deletes must include a tenant label: T_{tenant_id}" >&2
    echo "  Fix: Add the tenant label to your MATCH clause, e.g. MATCH (n:T_{\$tenant_id}:Person)" >&2
    exit 1
  fi
fi

# Neo4j: raw CREATE without tenant label
# Only flag if it looks like a direct Cypher CREATE (not a Python string assignment)
if echo "$COMMAND" | grep -qiE "cypher|neo4j|bolt://" && \
   echo "$COMMAND" | grep -qiE "CREATE\s+\("; then
  if ! echo "$COMMAND" | grep -qE "T_\{?[a-zA-Z_][a-zA-Z0-9_]*\}?|neo4j_facade|neofacade"; then
    echo "BLOCKED: Neo4j CREATE without tenant label or facade." >&2
    echo "  Command: $COMMAND" >&2
    echo "  Reason: All Neo4j writes must use neo4j_facade and include T_{tenant_id} label." >&2
    echo "  Fix: Use neo4j_facade.py methods, never raw driver. Labels: T_{\$tenant_id}." >&2
    exit 1
  fi
fi

# Filesystem: rm -rf on paths outside /tmp
if echo "$COMMAND" | grep -qE "rm\s+(-[a-zA-Z]*r[a-zA-Z]*\s+|--recursive\s+)"; then
  TARGET=$(echo "$COMMAND" | grep -oE "rm\s+(-[a-zA-Z]+\s+)*\S+" | tail -1 | awk '{print $NF}')
  if ! echo "$TARGET" | grep -qE "^/tmp/|^\./tmp/|node_modules|__pycache__|\.pyc$|dist/|build/"; then
    echo "BLOCKED: Recursive rm outside safe directories." >&2
    echo "  Command: $COMMAND" >&2
    echo "  Target: $TARGET" >&2
    echo "  Reason: rm -rf can cause irreversible data loss." >&2
    echo "  Fix: Use 'git clean -fd' for build artifacts, or be explicit about what to remove." >&2
    exit 1
  fi
fi

# Allow
exit 0
