# Pipeline stress test: 8 issues across risk tiers

**Date**: 2026-02-18
**Status**: Approved

## Purpose

Create 8 GitHub Issues to exercise the full AgentFactory pipeline and populate the outcome log with diverse data. The issues are real feature gaps, not synthetic tests. Two are intentionally vague to test the triage clarification flow.

## Issues

### 1. Remove dead workflow file

Delete `.github/workflows/agent-issue-trigger-simple.yml.disabled`. It was superseded by `agent-triage.yml` and serves no purpose. Remove any references in docs.

- **Risk**: high (touches `.github/workflows/`)
- **Expected outcome**: clean merge, trivial change

### 2. Add `/ready` endpoint for Cloud Run startup probes

The current `/health` endpoint always returns 200 regardless of configuration. Add a `/ready` endpoint that checks whether required environment variables (`CLICKUP_WEBHOOK_SECRET`, `CLICKUP_API_TOKEN`, `SLACK_WEBHOOK_URL`) are configured and returns 503 if any are missing. Cloud Run uses `/health` for liveness and `/ready` for startup probes.

- **Risk**: medium (touches `main.py`)
- **Expected outcome**: clean merge

### 3. Make dedup cache TTL and max size configurable

The `_DedupeCache` in `clickup.py` hardcodes `max_size=1000` and `ttl_seconds=3600`. Read these from `DEDUP_CACHE_MAX_SIZE` and `DEDUP_CACHE_TTL_SECONDS` env vars with the current values as defaults.

- **Risk**: high (touches `clickup.py`)
- **Expected outcome**: clean merge

### 4. Validate risk-policy.json schema at startup

Load and validate `risk-policy.json` during the FastAPI lifespan. Check that `riskTierRules` exists with valid tier names, that `mergePolicy` keys match, and that glob patterns are syntactically valid. Log a clear error and exit if validation fails.

- **Risk**: medium (touches `main.py`)
- **Expected outcome**: clean merge

### 5. Add retry with exponential backoff for Slack and ClickUp notifications

`_post_slack()` and `_post_clickup_comment()` in `callbacks.py` are one-shot. If the remote API returns 429 or a transient 5xx, the notification is silently dropped. Add retry logic with exponential backoff (3 attempts, base delay 1s). Use `tenacity` or hand-roll with `asyncio.sleep`.

- **Risk**: high (touches `callbacks.py`)
- **Expected outcome**: clean merge

### 6. Add Prometheus metrics endpoint

Add a `/metrics` endpoint that exposes request counts, error rates, and latency histograms using `prometheus-client`. Use the standard ASGI middleware pattern. This gives operators visibility into the orchestrator's health beyond structured logs.

- **Risk**: medium (touches `main.py`, adds `prometheus-client` dependency)
- **Expected outcome**: clean merge

### 7. Improve performance (intentionally vague)

"The orchestrator feels slow. Can you make it faster?"

No specific files, no metrics, no reproduction steps.

- **Risk**: unknown
- **Expected outcome**: triage asks a clarifying question

### 8. Refactor the webhook security model (intentionally vague + high-risk)

"The webhook security could be better. Maybe we should use something more modern?"

No specific proposal, touches security-sensitive code.

- **Risk**: high (routers)
- **Expected outcome**: triage asks a clarifying question

## Success criteria

After all 8 issues are processed:
- 6 PRs merged with outcome records (issues 1-6)
- 2 issues should have clarification comments (issues 7-8)
- `data/agent-outcomes.jsonl` has 6+ new records with non-empty `files_changed`
- Mix of high and medium risk tiers in the outcome log
- Pattern extraction has enough data to detect file-level patterns

## Cost estimate

~$0.30-0.50 per clear issue (triage + write + review), ~$0.10 per vague issue (triage only).
Total estimated: $2-4 for all 8 issues.
