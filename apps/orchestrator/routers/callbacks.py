"""
GitHub Actions callback handlers.

GitHub Actions workflows POST to these endpoints to report results.
All endpoints verify X-Callback-Secret to prevent spoofing.

Endpoints:
  POST /callbacks/agent-complete   — agent-write.yml finished (success or failure)
  POST /callbacks/review-clean     — agent-review.yml: no blocking findings
  POST /callbacks/blocked          — agent-review.yml OR agent-remediation.yml: escalation needed
"""

from __future__ import annotations

import asyncio
import hmac
import os
from typing import Any

import httpx
import structlog
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

logger = structlog.get_logger(__name__)

router = APIRouter()

# ── Configuration ──────────────────────────────────────────────────────────────
def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time, not import time. Enables testing and late binding."""
    return os.getenv(key, default)


# ── Request models ─────────────────────────────────────────────────────────────
class AgentCompletePayload(BaseModel):
    """Payload from agent-write.yml on completion (success or failure)."""

    clickup_task_id: str
    correlation_id: str = ""
    run_id: str = ""
    branch: str = ""
    pr_url: str = ""
    status: str = Field(default="unknown", pattern="^(success|failure|cancelled|unknown)$")


class ReviewCleanPayload(BaseModel):
    """Payload from agent-review.yml when no blocking findings."""

    pr_url: str
    pr_number: int
    branch: str = ""
    risk_tier: str = ""
    run_id: str = ""


class BlockedPayload(BaseModel):
    """Payload when a PR is blocked — review findings or max remediation rounds."""

    pr_url: str
    pr_number: int
    branch: str = ""
    reason: str = ""
    run_id: str = ""
    escalation: bool = False


# ── Secret verification ────────────────────────────────────────────────────────
def _verify_callback_secret(request: Request) -> None:
    """
    Verify the X-Callback-Secret header on inbound GitHub Actions callbacks.
    Raises HTTP 401 if the secret is wrong.
    Logs a warning (but allows) if no secret is configured in dev mode.
    """
    secret = _get_env("CALLBACK_SECRET")
    if not secret:
        if _get_env("ENVIRONMENT", "production") == "production":
            logger.warning(
                "callback_secret_not_configured",
                impact="All callback endpoints are publicly accessible. Set CALLBACK_SECRET.",
            )
        return

    provided = request.headers.get("X-Callback-Secret", "")
    # constant-time comparison prevents timing attacks
    if not hmac.compare_digest(secret.encode(), provided.encode()):
        logger.warning(
            "callback_secret_mismatch",
            client=request.client.host if request.client else "unknown",
            path=request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid callback secret",
        )


# ── Endpoints ──────────────────────────────────────────────────────────────────
@router.post("/agent-complete")
async def agent_complete(
    payload: AgentCompletePayload,
    request: Request,
) -> dict[str, Any]:
    """
    Callback from agent-write.yml on completion (always fires, success or failure).

    On success: logs the PR URL; review workflow will send the final notifications.
    On failure: posts Slack alert and ClickUp comment immediately.
    """
    _verify_callback_secret(request)

    log = logger.bind(
        clickup_task_id=payload.clickup_task_id,
        correlation_id=payload.correlation_id,
        run_id=payload.run_id,
        status=payload.status,
        branch=payload.branch,
    )
    log.info("agent_complete_callback", pr_url=payload.pr_url or "(no PR created)")

    if payload.status in ("failure", "cancelled"):
        github_repo = _get_env("GITHUB_REPO")
        actions_url = (
            f"https://github.com/{github_repo}/actions/runs/{payload.run_id}"
            if payload.run_id and github_repo
            else "(unknown run)"
        )
        await _post_slack(
            f"❌ *Agent write {payload.status}*\n"
            f"Task: `{payload.clickup_task_id}`\n"
            f"Branch: `{payload.branch}`\n"
            f"Run: <{actions_url}|{payload.run_id or 'view run'}>"
        )
        if payload.clickup_task_id:
            await _post_clickup_comment(
                payload.clickup_task_id,
                f"❌ Agent write {payload.status}.\n\n"
                f"GitHub Actions run: {actions_url}\n\n"
                f"Check the run logs to see what went wrong. "
                f"You may want to retry by removing and re-adding the `ai-agent` tag.",
            )

    elif payload.status == "success":
        log.info("agent_write_succeeded", pr_url=payload.pr_url)
        # Review workflow fires automatically on PR open and will send the
        # final notifications (review-clean or blocked). Nothing to do here.

    return {"ok": True, "received": payload.status}


@router.post("/review-clean")
async def review_clean(
    payload: ReviewCleanPayload,
    request: Request,
) -> dict[str, Any]:
    """
    Callback from agent-review.yml: PR passed all automated checks.
    Posts a ClickUp comment and Slack notification so humans know to review.
    """
    _verify_callback_secret(request)

    log = logger.bind(
        pr_url=payload.pr_url,
        pr_number=payload.pr_number,
        risk_tier=payload.risk_tier,
        run_id=payload.run_id,
    )
    log.info("review_clean_callback")

    task_id = _extract_task_id_from_branch(payload.branch)

    risk_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(payload.risk_tier, "⚪")

    # Post to ClickUp
    if task_id:
        await _post_clickup_comment(
            task_id,
            f"✅ PR ready for review: {payload.pr_url}\n\n"
            f"Risk tier: `{payload.risk_tier}`\n"
            f"All automated checks passed (risk gate, tests, Claude review, spec audit).\n\n"
            f"Ready for human review and merge.",
        )

    # Post to Slack
    slack_text = (
        f"✅ *Agent PR ready for review*\n"
        f"PR: <{payload.pr_url}|#{payload.pr_number}>\n"
        f"Risk: {risk_emoji} `{payload.risk_tier}`"
    )
    if task_id:
        slack_text += f"\nTask: `{task_id}`"

    await _post_slack(slack_text)

    log.info("review_clean_notifications_sent", task_id=task_id or "(none)")
    return {"ok": True}


@router.post("/blocked")
async def blocked(
    payload: BlockedPayload,
    request: Request,
) -> dict[str, Any]:
    """
    Callback when a PR needs human intervention.

    Two scenarios:
    1. Review found BLOCKING issues → remediation loop will handle it
       (this callback fires if remediation itself is blocked, not on first review finding)
    2. Max remediation rounds (2) exhausted → escalate to human immediately
    """
    _verify_callback_secret(request)

    task_id = _extract_task_id_from_branch(payload.branch)
    is_escalation = payload.escalation or payload.reason == "max-remediation-rounds"

    log = logger.bind(
        pr_url=payload.pr_url,
        pr_number=payload.pr_number,
        reason=payload.reason,
        escalation=is_escalation,
        task_id=task_id or "(none)",
    )
    log.warning("blocked_callback_received")

    if is_escalation:
        slack_text = (
            f"🛑 *Agent PR needs human review* — remediation limit reached\n"
            f"PR: <{payload.pr_url}|#{payload.pr_number}>\n"
            f"Reason: `{payload.reason}`\n"
            f"The automated fix loop ran 2 rounds. Blocking issues remain.\n"
            f"Please review and fix manually."
        )
        clickup_comment = (
            f"🛑 PR requires human review: {payload.pr_url}\n\n"
            f"AgentFactory ran 2 rounds of automated fixes but blocking issues remain.\n"
            f"Reason: {payload.reason}\n\n"
            f"Please review the BLOCKING findings in the PR comments and fix manually."
        )
    else:
        slack_text = (
            f"⚠️ *Agent PR blocked*\n"
            f"PR: <{payload.pr_url}|#{payload.pr_number}>\n"
            f"Reason: `{payload.reason}`"
        )
        if task_id:
            slack_text += f"\nTask: `{task_id}`"
        clickup_comment = (
            f"⚠️ Agent PR blocked: {payload.pr_url}\n\n"
            f"Reason: {payload.reason}"
        )

    await _post_slack(slack_text)

    if task_id:
        await _post_clickup_comment(task_id, clickup_comment)

    return {"ok": True}


# ── Notification helpers ───────────────────────────────────────────────────────
async def _post_slack(text: str) -> None:
    """
    Post a message to Slack via incoming webhook URL.

    Retries up to 3 times total (1 initial + 2 retries) with exponential backoff
    (1s, 2s delays). Only retries on network errors and 429/5xx responses.
    Logs and swallows errors — notification failure must not break the callback response.
    """
    slack_url = _get_env("SLACK_WEBHOOK_URL")
    slack_channel = _get_env("SLACK_CHANNEL", "dev-agents")
    if not slack_url:
        logger.debug(
            "slack_skipped",
            reason="SLACK_WEBHOOK_URL not configured",
            text_preview=text[:100],
        )
        return

    delays = [1.0, 2.0]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    slack_url,
                    json={"text": text, "channel": slack_channel},
                )
                resp.raise_for_status()
                logger.debug("slack_sent", channel=slack_channel)
                return
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                is_retriable = status_code == 429 or status_code >= 500
                if is_retriable and attempt < 2:
                    logger.debug(
                        "slack_retry",
                        attempt=attempt + 1,
                        status_code=status_code,
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                logger.warning(
                    "slack_post_failed",
                    status_code=status_code,
                    response_body=exc.response.text[:200],
                    error=str(exc),
                )
                return
            except httpx.RequestError as exc:
                if attempt < 2:
                    logger.debug(
                        "slack_retry",
                        attempt=attempt + 1,
                        error=str(exc),
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                logger.warning("slack_request_error", error=str(exc))
                return


async def _post_clickup_comment(task_id: str, comment_text: str) -> None:
    """
    Post a comment to a ClickUp task via the ClickUp API.

    Retries up to 3 times total (1 initial + 2 retries) with exponential backoff
    (1s, 2s delays). Only retries on network errors and 429/5xx responses.
    Logs and swallows errors — notification failure must not break the callback response.
    """
    clickup_token = _get_env("CLICKUP_API_TOKEN")
    if not clickup_token:
        logger.debug(
            "clickup_comment_skipped",
            reason="CLICKUP_API_TOKEN not configured",
            task_id=task_id,
        )
        return

    delays = [1.0, 2.0]
    async with httpx.AsyncClient(timeout=10.0) as client:
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"https://api.clickup.com/api/v2/task/{task_id}/comment",
                    headers={
                        "Authorization": clickup_token,
                        "Content-Type": "application/json",
                    },
                    json={"comment_text": comment_text, "notify_all": False},
                )
                resp.raise_for_status()
                logger.debug("clickup_comment_posted", task_id=task_id)
                return
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                is_retriable = status_code == 429 or status_code >= 500
                if is_retriable and attempt < 2:
                    logger.debug(
                        "clickup_retry",
                        attempt=attempt + 1,
                        task_id=task_id,
                        status_code=status_code,
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                logger.warning(
                    "clickup_comment_failed",
                    task_id=task_id,
                    status_code=status_code,
                    response_body=exc.response.text[:200],
                    error=str(exc),
                )
                return
            except httpx.RequestError as exc:
                if attempt < 2:
                    logger.debug(
                        "clickup_retry",
                        attempt=attempt + 1,
                        task_id=task_id,
                        error=str(exc),
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                logger.warning("clickup_request_error", task_id=task_id, error=str(exc))
                return


def _extract_task_id_from_branch(branch: str) -> str:
    """
    Extract the ClickUp task ID from a branch name.

    Expected branch format: agent/cu-{task_id}
    Examples:
        "agent/cu-abc123def"  →  "abc123def"
        "agent/cu-86bx3m"     →  "86bx3m"
        "main"                →  ""

    Returns empty string if the branch doesn't match the expected pattern.
    This is intentional — callers should handle missing task IDs gracefully.
    """
    if not branch:
        return ""
    last_segment = branch.rsplit("/", 1)[-1]
    if last_segment.startswith("cu-"):
        return last_segment[3:]
    return ""
