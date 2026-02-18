#!/usr/bin/env bash
# ── inject-env.sh — SessionStart hook ─────────────────────────────────────────
# Sets DATABASE_URL, NEO4J_URI, and other service URLs so the agent can run
# tests and interact with the stack without any manual configuration.
#
# Claude Code passes CLAUDE_ENV_FILE pointing to a temp file. Variables written
# there are injected into all subsequent Bash tool calls in this session.
#
# This hook runs once at session start. Keep it fast.
set -euo pipefail

# If CLAUDE_ENV_FILE isn't set, we're not running under Claude Code hooks.
# Exit cleanly — don't break local dev.
if [ -z "${CLAUDE_ENV_FILE:-}" ]; then
  exit 0
fi

# ── Service connection strings ─────────────────────────────────────────────────
# These match the GitHub Actions service container defaults in agent-write.yml.
# If your project uses different credentials, update these to match.

# PostgreSQL — matches postgres:15 service container config
cat >> "$CLAUDE_ENV_FILE" <<'EOF'
export DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app_test
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_DB=app_test
EOF

# Neo4j — matches neo4j:5.14 service container config
cat >> "$CLAUDE_ENV_FILE" <<'EOF'
export NEO4J_URI=bolt://localhost:7687
export NEO4J_USER=neo4j
export NEO4J_PASSWORD=testing123
export NEO4J_HTTP_URI=http://localhost:7474
EOF

# Redis
cat >> "$CLAUDE_ENV_FILE" <<'EOF'
export REDIS_URL=redis://localhost:6379
EOF

# ── Test environment flags ─────────────────────────────────────────────────────
cat >> "$CLAUDE_ENV_FILE" <<'EOF'
export TESTING=true
export ENVIRONMENT=test
EOF

# ── Application-specific vars ─────────────────────────────────────────────────
# Add your app-specific test env vars here.
# Example: JWT secret, API keys for test doubles, feature flags, etc.
#
# cat >> "$CLAUDE_ENV_FILE" <<'APPEOF'
# export JWT_SECRET=test_secret_not_for_production
# export FEATURE_FLAG_NEW_UI=false
# APPEOF

exit 0
