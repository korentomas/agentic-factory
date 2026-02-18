"""
Pattern Extraction — analyze agent outcomes to discover patterns and anti-patterns.

Reads data/agent-outcomes.jsonl and extracts recurring patterns from agent pipeline
runs. Generates .claude/rules/ files that Claude agents can read to improve future
performance.

This is pure data analysis — no Claude Agent SDK, no API calls.

Patterns detected:
  - File areas that are consistently handled well (3+ successful PRs)
  - Recurring failure modes (2+ PRs failing on the same check)
  - File hotspots that appear in failed PRs
  - Cost trends by outcome type

Architecture:
  1. load_outcomes() reads the JSONL log of all past agent runs.
  2. extract_patterns() finds recurring success signals (files, directories).
  3. extract_anti_patterns() finds recurring failure signals (checks, files).
  4. analyze() produces a full ExtractionReport with stats and insights.
  5. format_rules_markdown() renders the report as markdown.
  6. run_extraction() orchestrates the full pipeline and writes rules files.

Usage:
  python -m apps.orchestrator.jobs.pattern_extraction
  agentfactory-extract                          # after pip install -e .
  python scripts/extract_patterns.py            # convenience wrapper
  # Or via Cloud Run Job (set OUTCOMES_PATH env var for custom JSONL location)
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import structlog

logger = structlog.get_logger(__name__)


# ── Configuration ──────────────────────────────────────────────────────────────
def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time, not import time."""
    return os.getenv(key, default)


# ── Data types ─────────────────────────────────────────────────────────────────
@dataclass
class AgentOutcome:
    """Parsed outcome from agent-outcomes.jsonl."""

    outcome: str  # "clean", "tests-failed", "review-failed", "blocked"
    pr_url: str
    pr_number: int
    branch: str
    risk_tier: str
    checks: dict[str, str]
    files_changed: list[str]
    review_findings: list[str]
    run_id: str
    timestamp: str
    cost_usd: float = 0.0
    turns_total: int = 0


@dataclass
class Pattern:
    """An extracted pattern or anti-pattern."""

    kind: Literal["pattern", "anti-pattern"]
    description: str
    evidence_count: int  # How many outcomes support this
    evidence_prs: list[int]  # PR numbers
    confidence: float  # 0.0 to 1.0


@dataclass
class ExtractionReport:
    """Full extraction report from analyzing outcomes."""

    total_runs: int
    success_rate: float
    success_rate_by_tier: dict[str, float]
    common_failures: list[tuple[str, int]]  # (check_name, count)
    file_hotspots: list[tuple[str, int]]  # (file_path, failure_count)
    patterns: list[Pattern]
    anti_patterns: list[Pattern]
    period_start: str
    period_end: str
    cost_by_outcome: dict[str, float] = field(default_factory=dict)


# ── Loading ────────────────────────────────────────────────────────────────────
def load_outcomes(path: str = "data/agent-outcomes.jsonl") -> list[AgentOutcome]:
    """
    Load and parse all outcomes from the JSONL file.

    Each line is a JSON object representing one AgentOutcome.
    Malformed lines are skipped with a warning. Missing optional fields
    use their dataclass defaults. Returns an empty list if the file does
    not exist.
    """
    log = logger.bind(path=path)

    if not Path(path).exists():
        log.warning("outcomes_file_not_found", path=path)
        return []

    outcomes: list[AgentOutcome] = []
    with open(path, encoding="utf-8") as f:
        for line_num, raw_line in enumerate(f, start=1):
            stripped = raw_line.strip()
            if not stripped:
                continue
            try:
                data = json.loads(stripped)
            except json.JSONDecodeError:
                log.warning("malformed_outcome_line", line=line_num)
                continue

            try:
                outcome = AgentOutcome(
                    outcome=data["outcome"],
                    pr_url=data["pr_url"],
                    pr_number=data["pr_number"],
                    branch=data["branch"],
                    risk_tier=data["risk_tier"],
                    checks=data["checks"],
                    files_changed=data["files_changed"],
                    review_findings=data["review_findings"],
                    run_id=data["run_id"],
                    timestamp=data["timestamp"],
                    cost_usd=data.get("cost_usd", 0.0),
                    turns_total=data.get("turns_total", 0),
                )
                outcomes.append(outcome)
            except (KeyError, TypeError, ValueError) as exc:
                log.warning("outcome_parse_error", line=line_num, error=str(exc))
                continue

    log.info("outcomes_loaded", count=len(outcomes))
    return outcomes


# ── Pattern extraction ─────────────────────────────────────────────────────────
def extract_patterns(
    outcomes: list[AgentOutcome], min_evidence: int = 3
) -> list[Pattern]:
    """
    Extract positive patterns from successful outcomes.

    Groups by file paths — if the same files appear in min_evidence or more
    successful PRs, that area is well-handled by agents. Also groups by
    directory to identify broader well-understood areas.
    """
    successes = [o for o in outcomes if o.outcome == "clean"]
    if not successes:
        return []

    # Count file appearances across successful PRs
    file_counter: Counter[str] = Counter()
    file_prs: dict[str, list[int]] = {}
    for outcome in successes:
        for fpath in outcome.files_changed:
            file_counter[fpath] += 1
            file_prs.setdefault(fpath, []).append(outcome.pr_number)

    # Group by directory for area-level patterns
    dir_counter: Counter[str] = Counter()
    dir_prs: dict[str, list[int]] = {}
    for outcome in successes:
        dirs_seen: set[str] = set()
        for fpath in outcome.files_changed:
            parent = str(Path(fpath).parent)
            if parent not in dirs_seen:
                dirs_seen.add(parent)
                dir_counter[parent] += 1
                dir_prs.setdefault(parent, []).append(outcome.pr_number)

    patterns: list[Pattern] = []
    total_success = len(successes)

    # File-level patterns
    for filepath, count in file_counter.most_common():
        if count < min_evidence:
            break
        prs = file_prs[filepath]
        confidence = min(count / total_success, 1.0)
        patterns.append(
            Pattern(
                kind="pattern",
                description=(
                    f"File `{filepath}` has been successfully modified in "
                    f"{count} clean PRs — this area is well-handled."
                ),
                evidence_count=count,
                evidence_prs=prs,
                confidence=round(confidence, 2),
            )
        )

    # Directory-level patterns
    for dir_path, count in dir_counter.most_common():
        if count < min_evidence:
            break
        prs = sorted(set(dir_prs[dir_path]))
        confidence = min(count / total_success, 1.0)
        patterns.append(
            Pattern(
                kind="pattern",
                description=(
                    f"Directory `{dir_path}/` is consistently handled well "
                    f"across {count} successful PRs."
                ),
                evidence_count=count,
                evidence_prs=prs,
                confidence=round(confidence, 2),
            )
        )

    return patterns


# ── Anti-pattern extraction ────────────────────────────────────────────────────
def extract_anti_patterns(
    outcomes: list[AgentOutcome], min_evidence: int = 2
) -> list[Pattern]:
    """
    Extract anti-patterns from failed outcomes.

    Groups by failure check — if a check fails min_evidence or more times,
    notes which files are involved. Also identifies file-level hotspots
    across failed PRs.
    """
    failures = [o for o in outcomes if o.outcome != "clean"]
    if not failures:
        return []

    anti_patterns: list[Pattern] = []
    total_failures = len(failures)

    # Check-level anti-patterns: which checks fail most
    check_fail_count: Counter[str] = Counter()
    check_fail_prs: dict[str, list[int]] = {}
    check_fail_files: dict[str, Counter[str]] = {}
    for outcome in failures:
        for check_name, status in outcome.checks.items():
            if status == "failure":
                check_fail_count[check_name] += 1
                check_fail_prs.setdefault(check_name, []).append(outcome.pr_number)
                if check_name not in check_fail_files:
                    check_fail_files[check_name] = Counter()
                for fpath in outcome.files_changed:
                    check_fail_files[check_name][fpath] += 1

    for check_name, count in check_fail_count.most_common():
        if count < min_evidence:
            break
        prs = check_fail_prs[check_name]
        confidence = min(count / total_failures, 1.0)

        # Hint about the most commonly involved files for this failure
        top_files = check_fail_files.get(check_name, Counter()).most_common(3)
        file_hint = ""
        if top_files:
            file_list = ", ".join(f"`{fp}`" for fp, _ in top_files)
            file_hint = f" Files commonly involved: {file_list}."

        anti_patterns.append(
            Pattern(
                kind="anti-pattern",
                description=(
                    f"The `{check_name}` check has failed in {count} PRs."
                    f"{file_hint}"
                ),
                evidence_count=count,
                evidence_prs=prs,
                confidence=round(confidence, 2),
            )
        )

    # File-level anti-patterns: files appearing in multiple failed PRs
    file_fail_count: Counter[str] = Counter()
    file_fail_prs: dict[str, list[int]] = {}
    for outcome in failures:
        for fpath in outcome.files_changed:
            file_fail_count[fpath] += 1
            file_fail_prs.setdefault(fpath, []).append(outcome.pr_number)

    for fpath, count in file_fail_count.most_common():
        if count < min_evidence:
            break
        prs = file_fail_prs[fpath]
        confidence = min(count / total_failures, 1.0)
        anti_patterns.append(
            Pattern(
                kind="anti-pattern",
                description=(
                    f"File `{fpath}` appears in {count} failed PRs — "
                    f"changes here need extra care."
                ),
                evidence_count=count,
                evidence_prs=prs,
                confidence=round(confidence, 2),
            )
        )

    return anti_patterns


# ── Full analysis ──────────────────────────────────────────────────────────────
def analyze(outcomes: list[AgentOutcome]) -> ExtractionReport:
    """
    Full analysis producing an ExtractionReport.

    Computes success rates, failure modes, file hotspots, cost trends,
    patterns, and anti-patterns from the list of agent outcomes.
    """
    total = len(outcomes)
    if total == 0:
        return ExtractionReport(
            total_runs=0,
            success_rate=0.0,
            success_rate_by_tier={},
            common_failures=[],
            file_hotspots=[],
            patterns=[],
            anti_patterns=[],
            period_start="",
            period_end="",
            cost_by_outcome={},
        )

    # Success rate (as a fraction 0.0–1.0)
    successes = sum(1 for o in outcomes if o.outcome == "clean")
    success_rate = round(successes / total, 4)

    # Success rate by risk tier
    tier_totals: Counter[str] = Counter()
    tier_successes: Counter[str] = Counter()
    for o in outcomes:
        tier_totals[o.risk_tier] += 1
        if o.outcome == "clean":
            tier_successes[o.risk_tier] += 1

    success_rate_by_tier: dict[str, float] = {}
    for tier, tier_total in tier_totals.items():
        rate = tier_successes[tier] / tier_total if tier_total > 0 else 0.0
        success_rate_by_tier[tier] = round(rate, 4)

    # Common failure modes (which checks fail most)
    check_failures: Counter[str] = Counter()
    for o in outcomes:
        if o.outcome != "clean":
            for check_name, status in o.checks.items():
                if status == "failure":
                    check_failures[check_name] += 1
    common_failures = check_failures.most_common()

    # File hotspots — files appearing most in failed PRs
    file_fail_counter: Counter[str] = Counter()
    for o in outcomes:
        if o.outcome != "clean":
            for fpath in o.files_changed:
                file_fail_counter[fpath] += 1
    file_hotspots = file_fail_counter.most_common(10)

    # Period
    timestamps = sorted(o.timestamp for o in outcomes if o.timestamp)
    period_start = timestamps[0] if timestamps else ""
    period_end = timestamps[-1] if timestamps else ""

    # Patterns and anti-patterns
    patterns = extract_patterns(outcomes)
    anti_patterns = extract_anti_patterns(outcomes)

    # Cost trends: average cost per outcome type
    cost_by_outcome: dict[str, float] = {}
    outcome_cost_totals: dict[str, float] = {}
    outcome_cost_counts: dict[str, int] = {}
    for o in outcomes:
        if o.cost_usd > 0:
            outcome_cost_totals[o.outcome] = (
                outcome_cost_totals.get(o.outcome, 0.0) + o.cost_usd
            )
            outcome_cost_counts[o.outcome] = (
                outcome_cost_counts.get(o.outcome, 0) + 1
            )
    for outcome_type, total_cost in outcome_cost_totals.items():
        count = outcome_cost_counts[outcome_type]
        cost_by_outcome[outcome_type] = round(total_cost / count, 4)

    return ExtractionReport(
        total_runs=total,
        success_rate=success_rate,
        success_rate_by_tier=success_rate_by_tier,
        common_failures=common_failures,
        file_hotspots=file_hotspots,
        patterns=patterns,
        anti_patterns=anti_patterns,
        period_start=period_start,
        period_end=period_end,
        cost_by_outcome=cost_by_outcome,
    )


# ── Report formatting ─────────────────────────────────────────────────────────
def _format_pr_list(prs: list[int]) -> str:
    """Format a list of PR numbers as a compact string."""
    unique = sorted(set(prs))
    if len(unique) <= 3:
        return ", ".join(f"#{n}" for n in unique)
    return ", ".join(f"#{n}" for n in unique[:3]) + f" +{len(unique) - 3} more"


def format_rules_markdown(report: ExtractionReport) -> str:
    """
    Format the report as markdown suitable for .claude/rules/.

    Generates concise, actionable content that Claude agents can read to
    improve future performance. Kept under 50 lines of markdown.
    """
    if report.total_runs == 0:
        return "# Agent Patterns\n\nNo agent outcomes recorded yet.\n"

    lines: list[str] = []

    # Header
    lines.append("# Agent Pipeline Patterns")
    lines.append("")
    lines.append(
        f"Based on **{report.total_runs}** runs "
        f"({report.period_start} to {report.period_end}). "
        f"Overall success rate: **{report.success_rate:.0%}**."
    )
    lines.append("")

    # Success by tier
    if report.success_rate_by_tier:
        tier_parts = []
        for tier in ("low", "medium", "high"):
            rate = report.success_rate_by_tier.get(tier)
            if rate is not None:
                tier_parts.append(f"{tier}: {rate:.0%}")
        if tier_parts:
            lines.append(f"Success by risk tier: {', '.join(tier_parts)}.")
            lines.append("")

    # Patterns section
    if report.patterns:
        lines.append("## What Works Well")
        lines.append("")
        for p in report.patterns[:5]:
            lines.append(
                f"- {p.description} (PRs: {_format_pr_list(p.evidence_prs)})"
            )
        lines.append("")

    # Anti-patterns section
    if report.anti_patterns:
        lines.append("## Watch Out For")
        lines.append("")
        for ap in report.anti_patterns[:5]:
            lines.append(
                f"- {ap.description} (PRs: {_format_pr_list(ap.evidence_prs)})"
            )
        lines.append("")

    # Common failures
    if report.common_failures:
        lines.append("## Common Failure Checks")
        lines.append("")
        for check_name, count in report.common_failures[:5]:
            lines.append(f"- `{check_name}`: failed {count} time(s)")
        lines.append("")

    # File hotspots
    if report.file_hotspots:
        lines.append("## File Hotspots (frequent in failed PRs)")
        lines.append("")
        for fpath, count in report.file_hotspots[:5]:
            lines.append(f"- `{fpath}`: appeared in {count} failed PR(s)")
        lines.append("")

    # Cost trends
    if report.cost_by_outcome:
        lines.append("## Cost Trends (avg per run)")
        lines.append("")
        for outcome_type, avg_cost in sorted(report.cost_by_outcome.items()):
            lines.append(f"- {outcome_type}: ${avg_cost:.4f}")
        lines.append("")

    return "\n".join(lines)


def _split_patterns_markdown(report: ExtractionReport) -> tuple[str, str]:
    """
    Split the report into two markdown files: patterns and anti-patterns.

    Returns (patterns_md, anti_patterns_md).
    """
    # ── Patterns file ────────────────────────────────────────────────────────
    pat_lines: list[str] = []
    pat_lines.append("# Agent Patterns — What Works Well")
    pat_lines.append("")

    if report.total_runs == 0:
        pat_lines.append("No agent outcomes recorded yet.")
    else:
        pat_lines.append(
            f"Based on {report.total_runs} runs. "
            f"Success rate: {report.success_rate:.0%}."
        )
        pat_lines.append("")

        if report.success_rate_by_tier:
            for tier in ("low", "medium", "high"):
                rate = report.success_rate_by_tier.get(tier)
                if rate is not None:
                    pat_lines.append(f"- **{tier}** risk: {rate:.0%} success rate")
            pat_lines.append("")

        if report.patterns:
            for p in report.patterns[:5]:
                pat_lines.append(
                    f"- {p.description} "
                    f"(PRs: {_format_pr_list(p.evidence_prs)})"
                )
            pat_lines.append("")

        if report.cost_by_outcome:
            pat_lines.append("## Cost per Outcome")
            pat_lines.append("")
            for outcome_type, avg_cost in sorted(report.cost_by_outcome.items()):
                pat_lines.append(f"- {outcome_type}: ${avg_cost:.4f}")
            pat_lines.append("")

    patterns_md = "\n".join(pat_lines)

    # ── Anti-patterns file ───────────────────────────────────────────────────
    anti_lines: list[str] = []
    anti_lines.append("# Agent Anti-Patterns — Watch Out For")
    anti_lines.append("")

    if report.total_runs == 0:
        anti_lines.append("No agent outcomes recorded yet.")
    else:
        if report.anti_patterns:
            for ap in report.anti_patterns[:5]:
                anti_lines.append(
                    f"- {ap.description} "
                    f"(PRs: {_format_pr_list(ap.evidence_prs)})"
                )
            anti_lines.append("")
        else:
            anti_lines.append("No recurring anti-patterns detected yet.")
            anti_lines.append("")

        if report.common_failures:
            anti_lines.append("## Common Failure Checks")
            anti_lines.append("")
            for check_name, count in report.common_failures[:5]:
                anti_lines.append(f"- `{check_name}`: failed {count} time(s)")
            anti_lines.append("")

        if report.file_hotspots:
            anti_lines.append("## File Hotspots")
            anti_lines.append("")
            for fpath, count in report.file_hotspots[:5]:
                anti_lines.append(
                    f"- `{fpath}`: appeared in {count} failed PR(s) — "
                    f"when modifying this file, run tests early"
                )
            anti_lines.append("")

    anti_patterns_md = "\n".join(anti_lines)

    return patterns_md, anti_patterns_md


# ── Main entry point ──────────────────────────────────────────────────────────
async def run_extraction() -> int:
    """
    Main entry point. Reads outcomes, extracts patterns, writes rules files.

    1. Load outcomes from data/agent-outcomes.jsonl
    2. Analyze to produce an ExtractionReport
    3. Write .claude/rules/patterns.md and .claude/rules/anti-patterns.md
    4. Log summary

    Returns 0 on success, 1 on error.
    """
    log = logger.bind(job="pattern_extraction")
    outcomes_path = _get_env("OUTCOMES_PATH", "data/agent-outcomes.jsonl")
    rules_dir = _get_env("RULES_DIR", ".claude/rules")

    log.info("pattern_extraction_starting", outcomes_path=outcomes_path)

    # Step 1: load outcomes
    try:
        outcomes = load_outcomes(outcomes_path)
    except OSError as exc:
        log.error("outcomes_load_failed", error=str(exc))
        return 1

    if not outcomes:
        log.info("pattern_extraction_no_data", outcomes_path=outcomes_path)

    # Step 2: analyze (works on empty list too — produces zero-state report)
    report = analyze(outcomes)

    # Step 3: write rules files
    try:
        rules_path = Path(rules_dir)
        rules_path.mkdir(parents=True, exist_ok=True)

        patterns_md, anti_patterns_md = _split_patterns_markdown(report)

        patterns_file = rules_path / "patterns.md"
        patterns_file.write_text(patterns_md, encoding="utf-8")

        anti_patterns_file = rules_path / "anti-patterns.md"
        anti_patterns_file.write_text(anti_patterns_md, encoding="utf-8")

        log.info(
            "rules_files_written",
            patterns_file=str(patterns_file),
            anti_patterns_file=str(anti_patterns_file),
        )
    except OSError as exc:
        log.error("rules_write_failed", error=str(exc))
        return 1

    # Step 4: log summary
    log.info(
        "pattern_extraction_complete",
        total_runs=report.total_runs,
        success_rate=report.success_rate,
        patterns_found=len(report.patterns),
        anti_patterns_found=len(report.anti_patterns),
        common_failures=len(report.common_failures),
        file_hotspots=len(report.file_hotspots),
    )

    return 0


def main() -> None:
    """Entry point for CLI."""
    exit_code = asyncio.run(run_extraction())
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
