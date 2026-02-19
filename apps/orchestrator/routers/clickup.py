"""
ClickUp webhook handler.

Receives ClickUp webhook events, verifies HMAC-SHA256 signatures,
and dispatches `ai-agent`-tagged tasks to GitHub Actions.

Registration:
  POST https://api.clickup.com/api/v2/team/{team_id}/webhook
  { "endpoint": "https://your-service/webhooks/clickup", "events": ["taskTagUpdated"] }
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
from collections import OrderedDict
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, status

from apps.orchestrator.models import AgentTask

logger = structlog.get_logger(__name__)

router = APIRouter()

# ── Configuration ──────────────────────────────────────────────────────────────
def _get_env(key: str) -> str:
    """Read env var at call time, not import time. Enables testing and late binding."""
    return os.getenv(key, "")


def _parse_int_env(key: str, default: int) -> int:
    """Read an integer env var at call time. Returns default if unset or not a valid integer."""
    raw = os.getenv(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("invalid_int_env_var", key=key, value=raw, using_default=default)
        return default

# ── In-memory deduplication ────────────────────────────────────────────────────
# Prevents duplicate dispatches if ClickUp sends the same webhook twice.
# Uses an OrderedDict as a bounded LRU cache — no Redis dependency required.
# In production with multiple instances, use Redis instead.

class _DedupeCache:
    """Bounded in-memory cache for webhook deduplication."""

    def __init__(self, max_size: int = 1000, ttl_seconds: int = 3600) -> None:
        self._cache: OrderedDict[str, float] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds

    def is_duplicate(self, key: str) -> bool:
        now = time.time()
        if key in self._cache:
            if now - self._cache[key] < self._ttl:
                return True
            # Expired — remove it
            del self._cache[key]
        return False

    def mark_seen(self, key: str) -> None:
        now = time.time()
        self._cache[key] = now
        self._cache.move_to_end(key)
        # Evict oldest entries if over capacity
        while len(self._cache) > self._max_size:
            self._cache.popitem(last=False)


_dedupe: _DedupeCache | None = None


def _get_dedupe_cache() -> _DedupeCache:
    """Return the module-level dedup cache, initializing it from env vars on first use."""
    global _dedupe
    if _dedupe is None:
        _dedupe = _DedupeCache(
            max_size=_parse_int_env("DEDUP_CACHE_MAX_SIZE", 1000),
            ttl_seconds=_parse_int_env("DEDUP_CACHE_TTL_SECONDS", 3600),
        )
    return _dedupe


# ── Webhook endpoint ───────────────────────────────────────────────────────────
@router.post("/clickup")
async def clickup_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Receive ClickUp webhook events.

    Only processes taskTagUpdated events where the "ai-agent" tag was added.
    All other events are acknowledged but ignored.
    """
    # Read body FIRST — must happen before any other body access
    raw_body = await request.body()

    # ── Signature verification ─────────────────────────────────────────────────
    webhook_secret = _get_env("CLICKUP_WEBHOOK_SECRET")
    if webhook_secret:
        signature = request.headers.get("X-Signature", "")
        if not _verify_clickup_signature(raw_body, signature, webhook_secret):
            logger.warning(
                "clickup_webhook_invalid_signature",
                ip=request.client.host if request.client else "unknown",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )
    else:
        logger.warning(
            "clickup_webhook_secret_not_set",
            impact="Signature verification disabled. Set CLICKUP_WEBHOOK_SECRET before production.",
        )

    # ── Parse payload ──────────────────────────────────────────────────────────
    try:
        payload: dict[str, Any] = await request.json()
    except (ValueError, UnicodeDecodeError) as exc:
        logger.error("clickup_webhook_parse_error", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload",
        ) from exc

    event = payload.get("event", "")
    webhook_id = payload.get("webhook_id", "unknown")
    task_id = payload.get("task_id", "")

    logger.info(
        "clickup_webhook_received",
        clickup_event=event,
        webhook_id=webhook_id,
        task_id=task_id,
    )

    # ── Filter: only handle taskTagUpdated ────────────────────────────────────
    if event != "taskTagUpdated":
        return {"action": "ignored", "reason": f"event_type_{event}_not_handled"}

    # ── Filter: only handle "ai-agent" tag additions ──────────────────────────
    history_items: list[dict[str, Any]] = payload.get("history_items", [])
    ai_agent_added = any(
        item.get("field") == "tag"
        and isinstance(item.get("after"), dict)
        and item["after"].get("name") == "ai-agent"
        for item in history_items
    )

    if not ai_agent_added:
        return {"action": "ignored", "reason": "ai_agent_tag_not_added"}

    # ── Deduplication ─────────────────────────────────────────────────────────
    dedupe_key = f"clickup:{task_id}:ai-agent-tag"
    dedupe = _get_dedupe_cache()
    if dedupe.is_duplicate(dedupe_key):
        logger.info("clickup_webhook_duplicate", task_id=task_id)
        return {"action": "ignored", "reason": "duplicate_event"}

    dedupe.mark_seen(dedupe_key)

    # ── Dispatch in background (respond to ClickUp immediately) ───────────────
    # ClickUp has a short timeout for webhook acknowledgment.
    # Do the heavy lifting (ClickUp API call + GitHub dispatch) in background.
    background_tasks.add_task(_dispatch_task, task_id)

    logger.info(
        "clickup_webhook_accepted",
        task_id=task_id,
        action="dispatching",
    )
    return {"action": "dispatching", "task_id": task_id}


async def _dispatch_task(task_id: str) -> None:
    """
    Fetch task details from ClickUp and dispatch to GitHub Actions.
    Runs as a background task — errors are logged but don't affect the webhook response.
    """
    log = logger.bind(task_id=task_id)

    clickup_token = _get_env("CLICKUP_API_TOKEN")
    github_token = _get_env("GITHUB_APP_TOKEN")
    github_repo = _get_env("GITHUB_REPO")

    if not clickup_token:
        log.error("CLICKUP_API_TOKEN not set — cannot fetch task details")
        return

    if not github_token or not github_repo:
        log.error(
            "GitHub credentials not configured",
            has_token=bool(github_token),
            has_repo=bool(github_repo),
        )
        return

    # ── Fetch full task details ────────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(
                f"https://api.clickup.com/api/v2/task/{task_id}",
                headers={"Authorization": clickup_token},
            )
            resp.raise_for_status()
            task_details: dict[str, Any] = resp.json()
    except httpx.HTTPStatusError as exc:
        log.error(
            "clickup_api_error",
            status_code=exc.response.status_code,
            error=str(exc),
        )
        return
    except httpx.RequestError as exc:
        log.error("clickup_api_request_error", error=str(exc))
        return

    # ── Parse into AgentTask ───────────────────────────────────────────────────
    try:
        task = AgentTask.from_clickup_payload(task_id, task_details)
    except ValueError as exc:
        log.warning("agent_task_parse_failed", error=str(exc))
        return

    log.info(
        "agent_task_parsed",
        title=task.title[:80],
        risk_tier=task.risk_tier,
        complexity=task.complexity,
    )

    # ── Dispatch to GitHub Actions ─────────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{github_repo}/dispatches",
                headers={
                    "Authorization": f"Bearer {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                json={
                    "event_type": "agent-task",
                    "client_payload": task.to_dispatch_payload(),
                },
            )
            resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        log.error(
            "github_dispatch_error",
            status_code=exc.response.status_code,
            error=str(exc),
            response_body=exc.response.text[:500],
        )
        return
    except httpx.RequestError as exc:
        log.error("github_dispatch_request_error", error=str(exc))
        return

    log.info(
        "github_dispatch_sent",
        repo=github_repo,
        branch=task.branch,
        correlation_id=task.correlation_id,
    )


# ── Utilities ──────────────────────────────────────────────────────────────────
def _verify_clickup_signature(body: bytes, provided_signature: str, secret: str) -> bool:
    """
    Verify HMAC-SHA256 signature from ClickUp webhook.
    ClickUp sends the hex digest in X-Signature header.
    """
    if not provided_signature:
        return False

    expected = hmac.new(
        secret.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    return hmac.compare_digest(expected, provided_signature)
