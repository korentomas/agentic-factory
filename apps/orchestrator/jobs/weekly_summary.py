"""
Weekly Engineering Summary — Monday morning digest.

Runs as a Cloud Run Job triggered by Cloud Scheduler (every Monday at 09:00).

Architecture:
  1. This process gathers raw data directly (git stats, ClickUp API, pytest count).
  2. Passes the structured data to a Claude agent to write the narrative summary.
  3. The agent returns text. This process posts it to Slack.

The agent never needs credentials — it writes prose, not API calls.
All external I/O is owned by this Python process.

Usage:
  python -m apps.orchestrator.jobs.weekly_summary
  # Or via Cloud Run Job
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_CHANNEL = os.getenv("SLACK_CHANNEL", "dev-agents")
CLICKUP_API_TOKEN = os.getenv("CLICKUP_API_TOKEN", "")
CLICKUP_TEAM_ID = os.getenv("CLICKUP_TEAM_ID", "")
REPO_PATH = os.getenv("REPO_PATH", ".")


# ── Raw data collection ────────────────────────────────────────────────────────
@dataclass
class WeeklyStats:
    """Raw statistics gathered before calling the agent."""

    week_ending: str               # ISO date string
    total_merges: int
    agent_merges: int
    manual_merges: int
    recent_merge_subjects: list[str]   # Last 10 merge commit subjects
    total_test_count: int          # 0 if pytest not available
    large_files: list[str]         # Files >300 lines: ["path/to/file.py (342 lines)"]
    clickup_completed_count: int   # Tasks closed this week (0 if API not configured)
    clickup_completed_titles: list[str]


def _run_git(args: list[str], cwd: str = REPO_PATH) -> str:
    """
    Run a git command and return stdout as a stripped string.
    Returns empty string on any error (not running in a git repo, etc.).
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""


def _count_tests(cwd: str = REPO_PATH) -> int:
    """
    Count total collected tests via pytest --collect-only.
    Returns 0 if pytest is not installed or no tests found.
    """
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "--collect-only", "-q", "--no-header"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        # pytest --collect-only -q outputs: "<N> tests collected" or "<N> selected"
        for line in result.stdout.splitlines() + result.stderr.splitlines():
            if "selected" in line or "collected" in line:
                parts = line.strip().split()
                if parts and parts[0].isdigit():
                    return int(parts[0])
        return 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return 0


def _find_large_files(cwd: str = REPO_PATH) -> list[str]:
    """
    Find Python files >300 lines. Returns list of "path (N lines)" strings.
    Uses find + wc -l via subprocess.
    """
    try:
        result = subprocess.run(
            [
                "bash", "-c",
                "find . -name '*.py' -not -path './.git/*' -not -path '*/migrations/*' "
                "-not -path '*/__pycache__/*' "
                "| xargs wc -l 2>/dev/null "
                "| awk '$1 > 300 && $2 != \"total\" {print $2 \" (\" $1 \" lines)\"}' "
                "| sort -t'(' -k2 -rn "
                "| head -10"
            ],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
        return []
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return []


async def _fetch_clickup_completed(client: httpx.AsyncClient) -> tuple[int, list[str]]:
    """
    Fetch tasks closed in the last 7 days from ClickUp.
    Returns (count, list_of_titles). Returns (0, []) if API not configured.
    """
    if not CLICKUP_API_TOKEN or not CLICKUP_TEAM_ID:
        return 0, []

    # ClickUp API: get tasks updated in last 7 days with status "closed" or "complete"
    seven_days_ms = 7 * 24 * 60 * 60 * 1000
    now_ms = int(datetime.now(tz=timezone.utc).timestamp() * 1000)
    since_ms = now_ms - seven_days_ms

    try:
        # Get tasks across the team that were updated recently
        resp = await client.get(
            f"https://api.clickup.com/api/v2/team/{CLICKUP_TEAM_ID}/task",
            headers={"Authorization": CLICKUP_API_TOKEN},
            params={
                "date_updated_gt": since_ms,
                "statuses[]": ["closed", "complete", "done"],
                "subtasks": "true",
                "page": 0,
            },
            timeout=15.0,
        )
        resp.raise_for_status()
        tasks: list[dict[str, object]] = resp.json().get("tasks", [])
        titles = [str(t.get("name", "")) for t in tasks[:10]]  # Cap at 10 for display
        return len(tasks), titles
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("clickup_fetch_failed", error=str(exc))
        return 0, []


async def gather_stats() -> WeeklyStats:
    """
    Gather all raw stats. Network calls run concurrently.
    """
    week_ending = datetime.now(tz=timezone.utc).strftime("%Y-%m-%d")

    # Git stats (synchronous subprocess calls — run sequentially, fast)
    all_merges_raw = _run_git(["log", "--merges", "--since=7 days ago", "--format=%s"])
    all_merge_subjects = [s for s in all_merges_raw.splitlines() if s.strip()]
    total_merges = len(all_merge_subjects)

    agent_merges_raw = _run_git([
        "log", "--merges", "--since=7 days ago", "--format=%s",
        "--grep=agent/cu-",
    ])
    agent_merges = len([s for s in agent_merges_raw.splitlines() if s.strip()])
    manual_merges = total_merges - agent_merges

    # Recent merges for display (last 10, most recent first)
    recent_merge_subjects = all_merge_subjects[:10]

    # Test count and large files (subprocess, fast)
    total_test_count = _count_tests()
    large_files = _find_large_files()

    # ClickUp stats (async HTTP)
    async with httpx.AsyncClient(timeout=15.0) as client:
        cu_count, cu_titles = await _fetch_clickup_completed(client)

    return WeeklyStats(
        week_ending=week_ending,
        total_merges=total_merges,
        agent_merges=agent_merges,
        manual_merges=manual_merges,
        recent_merge_subjects=recent_merge_subjects,
        total_test_count=total_test_count,
        large_files=large_files,
        clickup_completed_count=cu_count,
        clickup_completed_titles=cu_titles,
    )


# ── Agent: write the narrative ─────────────────────────────────────────────────
def _build_summary_prompt(stats: WeeklyStats) -> str:
    """
    Build the prompt for the Claude agent, embedding the pre-gathered stats.
    The agent's only job is to write good prose from this structured data.
    """
    stats_json = json.dumps(asdict(stats), indent=2)
    return f"""
You are writing a weekly engineering digest for a software team.

Here is the raw data for the week ending {stats.week_ending}:

```json
{stats_json}
```

Write a clean, concise Slack message summarising this data. Use this structure:

*📊 Weekly Engineering Digest — {stats.week_ending}*

*Commits merged this week:* {{total_merges}} ({{agent_merges}} agent-written, {{manual_merges}} manual)
{{list up to 5 notable merges, one per bullet}}

*Tests:* {{total_test_count}} collected
*ClickUp tasks closed:* {{clickup_completed_count}}

*Codebase health:*
{{If any large files (>300 lines), list them. If none, say "No files over 300 lines ✅"}}

*Notable this week:*
{{1-2 sentences of insight or pattern you notice in the data. Be specific, not generic.
If agent-written PRs are high relative to total, note it.
If large file count increased, flag it.
If test count is low relative to codebase size, mention it.
If nothing notable, say "Quiet week."}}

Rules:
- Max 25 lines total.
- Plain text only — Slack-compatible (no HTML, no markdown tables).
- Use *bold* for section headers (Slack formatting).
- Use • for bullets.
- Do not invent numbers — only use the data provided above.
- Return ONLY the Slack message text. No preamble, no "Here's your summary:".
"""


async def _call_agent(prompt: str) -> str:
    """
    Call the Claude agent to generate the summary narrative.
    Returns the summary text. Raises RuntimeError on failure.
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query  # type: ignore[import]
    except ImportError as exc:
        raise RuntimeError(
            "claude-agent-sdk not installed. Run: pip install claude-agent-sdk"
        ) from exc

    collected_text: list[str] = []

    async for message in query(
        prompt=prompt,
        options=ClaudeAgentOptions(
            # No tools — pure text generation from provided data
            allowed_tools=[],
            max_turns=3,
        ),
    ):
        text: str | None = getattr(message, "text", None)
        if text:
            collected_text.append(text)

        result: str | None = getattr(message, "result", None)
        if result:
            collected_text.append(result)

    full_text = "\n".join(collected_text).strip()
    if not full_text:
        raise RuntimeError("Agent returned empty summary")

    return full_text


# ── Slack posting ──────────────────────────────────────────────────────────────
async def _post_to_slack(text: str) -> None:
    """
    Post the summary to Slack via incoming webhook.
    Raises httpx.HTTPStatusError on Slack API errors.
    """
    if not SLACK_WEBHOOK_URL:
        logger.info("slack_post_skipped", reason="SLACK_WEBHOOK_URL not set")
        print("[Slack not configured — printing to stdout instead]\n")
        print(text)
        return

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            SLACK_WEBHOOK_URL,
            json={"text": text, "channel": SLACK_CHANNEL},
        )
        resp.raise_for_status()
        logger.info("slack_post_sent", channel=SLACK_CHANNEL, chars=len(text))


# ── Main ───────────────────────────────────────────────────────────────────────
async def run_summary() -> int:
    """
    Generate and post the weekly engineering summary.
    Returns exit code: 0 = success, 1 = error.
    """
    log = logger.bind(job="weekly_summary")

    if not ANTHROPIC_API_KEY:
        log.error("ANTHROPIC_API_KEY not set")
        return 1

    log.info("weekly_summary_starting")

    # Step 1: gather raw data
    try:
        stats = await gather_stats()
        log.info(
            "stats_gathered",
            total_merges=stats.total_merges,
            agent_merges=stats.agent_merges,
            tests=stats.total_test_count,
            large_files=len(stats.large_files),
            clickup_closed=stats.clickup_completed_count,
        )
    except Exception as exc:
        log.error("stats_gather_failed", error=str(exc), exc_info=True)
        return 1

    # Step 2: generate narrative with agent
    try:
        prompt = _build_summary_prompt(stats)
        summary_text = await _call_agent(prompt)
        log.info("summary_generated", chars=len(summary_text))
    except RuntimeError as exc:
        log.error("agent_failed", error=str(exc))
        # Fall back to a minimal machine-generated summary — don't fail silently
        summary_text = (
            f"*📊 Weekly Engineering Digest — {stats.week_ending}*\n\n"
            f"*Commits merged:* {stats.total_merges} "
            f"({stats.agent_merges} agent-written, {stats.manual_merges} manual)\n"
            f"*Tests:* {stats.total_test_count} collected\n"
            f"*ClickUp tasks closed:* {stats.clickup_completed_count}\n\n"
            f"_(Agent narrative unavailable this week)_"
        )
    except Exception as exc:
        log.error("agent_unexpected_error", error=str(exc), exc_info=True)
        return 1

    # Step 3: post to Slack
    try:
        await _post_to_slack(summary_text)
    except httpx.HTTPStatusError as exc:
        log.error(
            "slack_post_failed",
            status_code=exc.response.status_code,
            response_body=exc.response.text[:200],
        )
        # Log the summary even if Slack fails
        log.info("summary_text", text=summary_text)
        return 1
    except Exception as exc:
        log.error("slack_unexpected_error", error=str(exc), exc_info=True)
        return 1

    log.info("weekly_summary_complete")
    return 0


def main() -> None:
    """Entry point for Cloud Run Job and CLI."""
    exit_code = asyncio.run(run_summary())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
