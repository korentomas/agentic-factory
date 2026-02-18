"""
Codebase Scanner — weekly autonomous audit of the target repository.

Runs as a Cloud Run Job, triggered by Cloud Scheduler (e.g., every Sunday night).
Uses the Claude Agent SDK to scan the codebase for issues, then this process
creates the ClickUp tickets directly via the ClickUp API.

Separation of concerns:
  - The agent scans code and emits structured FINDING lines to its output.
  - This Python process parses those findings and calls the ClickUp API.
  - The agent never needs credentials injected into its prompt.

Issues detected:
  - Endpoints missing authentication
  - Neo4j queries without tenant labels
  - Blocking sync calls in async context
  - Test coverage gaps for route handlers
  - Files >300 lines (degrades agent navigation)
  - Violations of anti-patterns listed in CLAUDE.md

Usage:
  python -m apps.orchestrator.jobs.codebase_scan
  # Or via Cloud Run Job (set REPO_PATH env var to the checked-out target repo)
"""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Literal

import httpx
import structlog

logger = structlog.get_logger(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time, not import time."""
    return os.getenv(key, default)

# Priority mapping: ClickUp uses 1=urgent, 2=high, 3=normal, 4=low
_CLICKUP_PRIORITY: dict[str, int] = {
    "high": 2,
    "medium": 3,
    "low": 4,
}

# ── Finding data type ──────────────────────────────────────────────────────────
@dataclass
class Finding:
    """
    A structured code issue found by the scanner.

    Format emitted by the agent (one per line):
      FINDING: <category> | <severity> | <file:line> | <description>

    Example:
      FINDING: missing-auth | high | apps/api/routers/users.py:42
        | POST /users/bulk has no verify_token dependency
    """

    category: str
    severity: Literal["high", "medium", "low"]
    location: str  # file:line
    description: str
    raw_line: str

    @classmethod
    def parse(cls, line: str) -> Finding | None:
        """
        Parse a FINDING: line emitted by the Claude agent.
        Returns None if the line doesn't match the expected format.
        """
        if not line.startswith("FINDING:"):
            return None

        # Strip the prefix and split on " | "
        body = line[len("FINDING:"):].strip()
        parts = [p.strip() for p in body.split("|")]

        if len(parts) < 4:
            return None

        category = parts[0].lower().replace(" ", "-")
        raw_severity = parts[1].lower().strip()
        _valid_severities: dict[str, Literal["high", "medium", "low"]] = {
            "high": "high", "medium": "medium", "low": "low",
        }
        severity: Literal["high", "medium", "low"] = _valid_severities.get(
            raw_severity, "medium"
        )
        location = parts[2]
        description = " | ".join(parts[3:])  # rejoin in case description had pipes

        return cls(
            category=category,
            severity=severity,
            location=location,
            description=description,
            raw_line=line,
        )

    def to_clickup_title(self) -> str:
        return f"[Scan] {self.category}: {self.description[:80]}"

    def to_clickup_description(self) -> str:
        return (
            f"**Automated finding from weekly codebase scan**\n\n"
            f"**Category:** {self.category}\n"
            f"**Severity:** {self.severity}\n"
            f"**Location:** `{self.location}`\n\n"
            f"**Description:**\n{self.description}\n\n"
            f"---\n"
            f"This ticket was auto-created by AgentFactory's weekly scanner. "
            f"It has been tagged `ai-agent` so AgentFactory can auto-fix it. "
            f"Remove the tag if you want to handle it manually."
        )


# ── Scanner agent prompt ───────────────────────────────────────────────────────
# The agent scans and ONLY emits FINDING: lines — it does not make API calls.
# Credentials are not in the prompt.
def _build_scan_prompt() -> str:
    """Build the scanner prompt with current env var values."""
    repo_path = _get_env("REPO_PATH", ".")
    return f"""
You are performing a weekly automated codebase audit of a Python/FastAPI codebase.
Your working directory is: {repo_path}

Find real bugs, security gaps, and maintenance problems. Not style preferences.

## Scan categories

### 1. Missing Authentication
Look for FastAPI route handlers (@router.get, @router.post, etc.) that have no
auth dependency (verify_token, get_current_user, Depends(auth), etc.).
Exempt: /health, /metrics, /docs endpoints.

How to scan:
  grep -rn "@router\\." apps/ --include="*.py" | grep -v "test_"
  Then for each router file, check if the function has an auth dependency.

### 2. Tenant Isolation Violations
Look for Neo4j Cypher queries that don't include a T_{{tenant}} label pattern.
Also look for `from neo4j import` or `driver.session()` outside of any file
named *facade* or *neo4j*.

How to scan:
  grep -rn "MATCH\\|CREATE\\|MERGE" apps/ --include="*.py" | grep -v "T_"
  grep -rn "from neo4j import\\|neo4j.GraphDatabase" apps/ --include="*.py"

### 3. Sync/Async Violations
Look for: `asyncio.run(` called inside an async function.
Look for: sync database calls (`.execute(` without `await`) inside `async def` functions.

How to scan:
  grep -rn "asyncio.run(" apps/ --include="*.py"
  grep -B5 "\\.execute(" apps/ --include="*.py" | grep -B5 "async def"

### 4. Test Coverage Gaps
Look for router files in apps/*/routers/ that have no corresponding test file.

How to scan:
  ls apps/*/routers/*.py 2>/dev/null | grep -v __init__ | grep -v test_
  ls apps/*/tests/test_*.py 2>/dev/null || echo "no tests found"

### 5. Large Files (>300 lines)
Large files degrade agent performance. Find them.

How to scan:
  find {repo_path} -name "*.py" -not -path "*/.git/*" -not -path "*/migrations/*" \\
    | xargs wc -l 2>/dev/null | sort -rn | awk '$1 > 300 && $2 != "total"' | head -10

### 6. Deprecated Patterns
If CLAUDE.md exists at the repo root, read it. Find code violating its anti-patterns section.

## Output format

For each finding, emit exactly one line in this format:
  FINDING: <category> | <severity: high/medium/low> | <file:line> | <description>

Examples:
  FINDING: missing-auth | high | apps/routers/contacts.py:87 | POST /contacts/import has no auth
  FINDING: large-file | low | apps/services/sync.py:1 | File is 512 lines — split into modules
  FINDING: tenant-isolation | high | apps/services/graph.py:203 | MATCH (n:Person) missing T_ label

Rules:
- One FINDING: line per issue. Do not group multiple issues into one line.
- Be specific about file and line number.
- Description must be a single line.
- Severity: high=security/data-loss risk, medium=correctness risk, low=maintenance.
- After all findings, print: SCAN_COMPLETE: <N> findings across <K> categories

Do not create tickets, call APIs, or do anything other than scan and emit FINDING: lines.
"""


# ── Agent runner ───────────────────────────────────────────────────────────────
async def _run_agent() -> list[Finding]:
    """
    Run the Claude scanner agent and collect all FINDING: lines from its output.
    Returns a list of parsed Finding objects.
    """
    try:
        from claude_agent_sdk import ClaudeAgentOptions, query
    except ImportError as exc:
        raise RuntimeError(
            "claude-agent-sdk not installed. Run: pip install claude-agent-sdk"
        ) from exc

    findings: list[Finding] = []
    raw_output_lines: list[str] = []

    async for message in query(
        prompt=_build_scan_prompt(),
        options=ClaudeAgentOptions(
            allowed_tools=["Read", "Glob", "Grep", "Bash"],
            max_turns=50,
            permission_mode="bypassPermissions",
        ),
    ):
        # Collect all text output — FINDING: lines are in the agent's text output
        text: str | None = getattr(message, "text", None)
        if text:
            for line in text.splitlines():
                raw_output_lines.append(line)
                finding = Finding.parse(line)
                if finding is not None:
                    findings.append(finding)
                    logger.info(
                        "finding_parsed",
                        category=finding.category,
                        severity=finding.severity,
                        location=finding.location,
                    )

        # Also check result field (final message)
        result: str | None = getattr(message, "result", None)
        if result:
            for line in result.splitlines():
                if line.startswith("FINDING:"):
                    finding = Finding.parse(line)
                    if finding is not None and finding.raw_line not in {
                        f.raw_line for f in findings
                    }:
                        findings.append(finding)

    return findings


# ── ClickUp ticket creation ────────────────────────────────────────────────────
async def _create_clickup_ticket(finding: Finding, client: httpx.AsyncClient) -> bool:
    """
    Create a ClickUp task for a finding in the backlog list.
    Returns True if created successfully, False on error.
    """
    backlog_list_id = _get_env("CLICKUP_BACKLOG_LIST_ID")
    clickup_token = _get_env("CLICKUP_API_TOKEN")

    if not backlog_list_id or not clickup_token:
        logger.debug(
            "clickup_ticket_skipped",
            reason="CLICKUP_BACKLOG_LIST_ID or CLICKUP_API_TOKEN not configured",
            finding=finding.category,
        )
        return False

    try:
        resp = await client.post(
            f"https://api.clickup.com/api/v2/list/{backlog_list_id}/task",
            headers={
                "Authorization": clickup_token,
                "Content-Type": "application/json",
            },
            json={
                "name": finding.to_clickup_title(),
                "description": finding.to_clickup_description(),
                "tags": ["ai-agent", "auto-scan"],
                "priority": _CLICKUP_PRIORITY.get(finding.severity, 3),
            },
        )
        resp.raise_for_status()
        task_data: dict[str, object] = resp.json()
        task_id = task_data.get("id", "unknown")
        logger.info(
            "clickup_ticket_created",
            task_id=task_id,
            category=finding.category,
            severity=finding.severity,
            location=finding.location,
        )
        return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "clickup_ticket_failed",
            status_code=exc.response.status_code,
            response_body=exc.response.text[:300],
            finding=finding.category,
        )
        return False
    except httpx.RequestError as exc:
        logger.error("clickup_request_error", error=str(exc), finding=finding.category)
        return False


# ── Deduplication: check for existing open tickets ────────────────────────────
async def _fetch_existing_scan_tickets(client: httpx.AsyncClient) -> set[str]:
    """
    Fetch existing open tickets tagged 'auto-scan' to avoid duplicates.
    Returns a set of title strings (lowercased) for fuzzy deduplication.
    """
    backlog_list_id = _get_env("CLICKUP_BACKLOG_LIST_ID")
    clickup_token = _get_env("CLICKUP_API_TOKEN")

    if not backlog_list_id or not clickup_token:
        return set()

    try:
        resp = await client.get(
            f"https://api.clickup.com/api/v2/list/{backlog_list_id}/task",
            headers={"Authorization": clickup_token},
            params={"tags[]": "auto-scan", "statuses[]": "open", "page": 0},
        )
        resp.raise_for_status()
        tasks: list[dict[str, object]] = resp.json().get("tasks", [])
        return {str(t.get("name", "")).lower() for t in tasks}
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("clickup_fetch_existing_failed", error=str(exc))
        return set()


def _is_duplicate(finding: Finding, existing_titles: set[str]) -> bool:
    """
    Fuzzy-check if a finding already has an open ticket.
    Matches on category + location (not full description) to catch rewording.
    """
    key = f"{finding.category}: {finding.location}".lower()
    return any(key in title for title in existing_titles)


# ── Main ───────────────────────────────────────────────────────────────────────
async def run_scan() -> int:
    """
    Run the weekly codebase scan.
    Returns exit code: 0 = success (even if findings exist), 1 = hard error.
    """
    log = logger.bind(job="codebase_scan", repo_path=_get_env("REPO_PATH", "."))

    if not _get_env("ANTHROPIC_API_KEY"):
        log.error("ANTHROPIC_API_KEY not set")
        return 1

    log.info("codebase_scan_starting")

    # Run the agent
    try:
        findings = await _run_agent()
    except RuntimeError as exc:
        log.error("agent_run_failed", error=str(exc))
        return 1
    except Exception as exc:
        log.error("agent_run_unexpected_error", error=str(exc), exc_info=True)
        return 1

    if not findings:
        log.info("codebase_scan_complete", total_findings=0)
        return 0

    log.info("codebase_scan_findings_collected", total=len(findings))

    # Create ClickUp tickets
    async with httpx.AsyncClient(timeout=15.0) as client:
        existing_titles = await _fetch_existing_scan_tickets(client)

        created = 0
        skipped_duplicate = 0

        for finding in findings:
            if _is_duplicate(finding, existing_titles):
                log.info(
                    "finding_skipped_duplicate",
                    category=finding.category,
                    location=finding.location,
                )
                skipped_duplicate += 1
                continue

            success = await _create_clickup_ticket(finding, client)
            if success:
                created += 1
            # Add to existing titles so subsequent findings don't duplicate within this run
            existing_titles.add(finding.to_clickup_title().lower())

    log.info(
        "codebase_scan_complete",
        total_findings=len(findings),
        tickets_created=created,
        duplicates_skipped=skipped_duplicate,
    )

    # Print summary to stdout (visible in Cloud Run Job logs)
    print("\n=== Codebase Scan Summary ===")
    print(f"Total findings: {len(findings)}")
    print(f"Tickets created: {created}")
    print(f"Duplicates skipped: {skipped_duplicate}")
    by_severity: dict[str, int] = {}
    for f in findings:
        by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
    for sev, count in sorted(by_severity.items()):
        print(f"  {sev}: {count}")
    print()

    return 0


def main() -> None:
    """Entry point for Cloud Run Job and CLI."""
    exit_code = asyncio.run(run_scan())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
