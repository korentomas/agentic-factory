#!/usr/bin/env python3
"""
Risk Policy Gate — determines risk tier from changed file paths.

Reads risk-policy.json, evaluates changed files against glob patterns,
outputs the tier and required checks, and sets GitHub Actions step outputs.

Usage:
    python scripts/risk_policy_gate.py \\
        --changed-files "apps/api/app/auth/jwt.py apps/api/app/routers/users.py" \\
        --policy risk-policy.json \\
        --output-format github-actions

Exit codes:
    0 — gate passed (PR may proceed to next checks)
    1 — gate blocked (PR is blocked, e.g. by a blockedPatterns match)

GitHub Actions step outputs (when --output-format github-actions):
    tier            — high | medium | low
    required_checks — JSON array of check names
    blocked         — true | false
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


def load_policy(policy_path: str) -> dict[str, Any]:
    """Load and validate the risk policy JSON file."""
    path = Path(policy_path)
    if not path.exists():
        print(f"ERROR: Policy file not found: {policy_path}", file=sys.stderr)
        sys.exit(1)

    try:
        with path.open() as f:
            policy: dict[str, Any] = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON in policy file: {exc}", file=sys.stderr)
        sys.exit(1)

    # Validate required keys
    if "riskTierRules" not in policy:
        print("ERROR: Policy missing 'riskTierRules' key", file=sys.stderr)
        sys.exit(1)
    if "mergePolicy" not in policy:
        print("ERROR: Policy missing 'mergePolicy' key", file=sys.stderr)
        sys.exit(1)

    return policy


def parse_changed_files(raw: str) -> list[str]:
    """
    Parse the --changed-files argument into a list of file paths.
    Handles space-separated, newline-separated, or mixed input.
    Filters empty strings and strips leading/trailing whitespace.
    """
    # Normalize: replace newlines with spaces, then split
    normalized = raw.replace("\n", " ").replace("\r", " ")
    files = [f.strip() for f in normalized.split() if f.strip()]
    return files


def match_glob(file_path: str, pattern: str) -> bool:
    """
    Match a file path against a glob pattern.

    Supports:
    - Standard fnmatch patterns: *.py, *.cypher
    - Directory patterns: apps/api/app/auth/**
    - Double-star (**) for recursive matching

    We implement ** manually because fnmatch doesn't support it natively.
    """
    # Normalize path separators
    file_path = file_path.replace("\\", "/")
    pattern = pattern.replace("\\", "/")

    # Direct match first (handles patterns without globs)
    if fnmatch.fnmatch(file_path, pattern):
        return True

    # Handle ** patterns by converting to regex
    if "**" in pattern:
        # Convert glob pattern to regex:
        # **  → matches anything including path separators
        # *   → matches anything except path separators
        # ?   → matches a single character except /
        # .   → literal dot

        # Escape the pattern for regex, then unescape our glob chars
        regex_parts: list[str] = []
        i = 0
        while i < len(pattern):
            if pattern[i : i + 3] == "**/":
                # **/ at start or middle: match zero or more path components
                regex_parts.append("(?:.+/)?")
                i += 3
            elif pattern[i : i + 2] == "**":
                # ** at end: match everything
                regex_parts.append(".+")
                i += 2
            elif pattern[i] == "*":
                # Single * matches anything except /
                regex_parts.append("[^/]*")
                i += 1
            elif pattern[i] == "?":
                regex_parts.append("[^/]")
                i += 1
            elif pattern[i] == ".":
                regex_parts.append(r"\.")
                i += 1
            else:
                regex_parts.append(re.escape(pattern[i]))
                i += 1

        regex = "^" + "".join(regex_parts) + "$"
        try:
            return bool(re.match(regex, file_path))
        except re.error:
            # Malformed pattern — fall back to fnmatch
            return fnmatch.fnmatch(file_path, pattern)

    # Also try matching the basename alone against simple patterns (no path sep)
    if "/" not in pattern:
        basename = file_path.split("/")[-1]
        return fnmatch.fnmatch(basename, pattern)

    return False


def determine_tier(
    changed_files: list[str],
    tier_rules: dict[str, list[str]],
) -> str:
    """
    Determine the highest risk tier across all changed files.

    Tier priority: high > medium > low
    A single high-risk file makes the entire PR high-risk.

    Args:
        changed_files: List of relative file paths changed in the PR.
        tier_rules: Dict mapping tier name → list of glob patterns.

    Returns:
        "high", "medium", or "low"
    """
    # Tier priority order — highest wins
    tier_order = ["high", "medium", "low"]

    # Track which tier we've escalated to
    highest_tier = "low"
    highest_tier_idx = tier_order.index("low")

    # Track which files matched which tier (for reporting)
    matches: dict[str, list[str]] = {tier: [] for tier in tier_order}

    for file_path in changed_files:
        for tier in tier_order:
            if tier not in tier_rules:
                continue
            patterns: list[str] = tier_rules[tier]
            for pattern in patterns:
                if match_glob(file_path, pattern):
                    matches[tier].append(file_path)
                    tier_idx = tier_order.index(tier)
                    if tier_idx < highest_tier_idx:
                        highest_tier = tier
                        highest_tier_idx = tier_idx
                    break  # First matching pattern wins for this file+tier

    return highest_tier


def check_blocked_patterns(
    changed_files: list[str],
    blocked_patterns: list[dict[str, str]],
) -> list[dict[str, str]]:
    """
    Check if any changed files match blocked patterns that should hard-stop the PR.

    Returns a list of violations (empty = no violations).
    Each violation is {"file": ..., "pattern": ..., "reason": ...}
    """
    violations: list[dict[str, str]] = []

    # Note: blockedPatterns in the policy match on *file content*, not path.
    # Path-based blocking is handled by tier escalation.
    # This function checks path-based blocked patterns specifically.
    for entry in blocked_patterns:
        pattern = entry.get("pattern", "")
        reason = entry.get("reason", "Blocked pattern")
        tier = entry.get("tier", "high")

        if not pattern:
            continue

        # Path-based check: does any changed file path match this pattern?
        for file_path in changed_files:
            if match_glob(file_path, pattern):
                violations.append(
                    {
                        "file": file_path,
                        "pattern": pattern,
                        "reason": reason,
                        "tier": tier,
                    }
                )

    return violations


def write_github_outputs(outputs: dict[str, str]) -> None:
    """
    Write key=value pairs to the GitHub Actions $GITHUB_OUTPUT file.
    Falls back to printing if not in a GitHub Actions environment.
    """
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as f:
            for key, value in outputs.items():
                # Multi-line values use heredoc syntax
                if "\n" in value:
                    f.write(f"{key}<<EOF\n{value}\nEOF\n")
                else:
                    f.write(f"{key}={value}\n")
    else:
        # Not in GitHub Actions — print to stdout for local testing
        for key, value in outputs.items():
            print(f"::set-output name={key}::{value}")


def print_summary(
    tier: str,
    changed_files: list[str],
    required_checks: list[str],
    blocked: bool,
    violations: list[dict[str, str]],
    tier_rules: dict[str, list[str]],
) -> None:
    """Print a human-readable summary of the gate result."""
    tier_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(tier, "⚪")

    print(f"\n{'='*60}")
    print("Risk Policy Gate Result")
    print(f"{'='*60}")
    print(f"Tier:     {tier_emoji} {tier.upper()}")
    print(f"Blocked:  {'YES ❌' if blocked else 'NO ✅'}")
    print(f"Files:    {len(changed_files)} changed")
    print("\nRequired checks:")
    for check in required_checks:
        print(f"  • {check}")

    if violations:
        print(f"\nBlocklist violations ({len(violations)}):")
        for v in violations:
            print(f"  ❌ {v['file']}: {v['reason']}")

    print("\nFile breakdown:")
    for file_path in changed_files[:20]:  # Show max 20 files
        # Find which tier matched this file
        matched_tier = "low"  # default
        for t in ["high", "medium"]:
            if t in tier_rules:
                for pattern in tier_rules[t]:
                    if match_glob(file_path, pattern):
                        matched_tier = t
                        break
        tier_marker = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(matched_tier, "⚪")
        print(f"  {tier_marker} {file_path}")

    if len(changed_files) > 20:
        print(f"  ... and {len(changed_files) - 20} more files")

    print(f"{'='*60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Risk policy gate for AgentFactory PR review pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--changed-files",
        required=True,
        help=(
            "Space or newline-separated list of changed file paths. "
            "Pass the output of: git diff --name-only origin/main...HEAD"
        ),
    )
    parser.add_argument(
        "--policy",
        default="risk-policy.json",
        help="Path to the risk policy JSON file (default: risk-policy.json)",
    )
    parser.add_argument(
        "--output-format",
        choices=["text", "json", "github-actions"],
        default="text",
        help=(
            "Output format. "
            "'github-actions' writes to $GITHUB_OUTPUT for step output variables."
        ),
    )

    args = parser.parse_args()

    # ── Load policy ────────────────────────────────────────────────────────────
    policy = load_policy(args.policy)
    tier_rules: dict[str, list[str]] = policy["riskTierRules"]
    merge_policy: dict[str, dict[str, Any]] = policy["mergePolicy"]
    blocked_patterns: list[dict[str, str]] = policy.get("blockedPatterns", [])

    # ── Parse changed files ────────────────────────────────────────────────────
    changed_files = parse_changed_files(args.changed_files)

    if not changed_files:
        # No files changed — gate passes at low tier
        print("WARNING: No changed files provided. Defaulting to low tier.", file=sys.stderr)
        tier = "low"
    else:
        # ── Determine risk tier ────────────────────────────────────────────────
        tier = determine_tier(changed_files, tier_rules)

    # ── Check blocked patterns ─────────────────────────────────────────────────
    violations = check_blocked_patterns(changed_files, blocked_patterns)
    blocked = len(violations) > 0

    # ── Get required checks for this tier ─────────────────────────────────────
    tier_policy = merge_policy.get(tier, merge_policy.get("low", {}))
    required_checks: list[str] = tier_policy.get("requiredChecks", ["risk-policy-gate"])
    human_approval_required: bool = tier_policy.get("humanApprovalRequired", False)

    # ── Output ─────────────────────────────────────────────────────────────────
    if args.output_format == "json":
        result = {
            "tier": tier,
            "blocked": blocked,
            "required_checks": required_checks,
            "human_approval_required": human_approval_required,
            "changed_files_count": len(changed_files),
            "violations": violations,
        }
        print(json.dumps(result, indent=2))

    elif args.output_format == "github-actions":
        # Print human summary to stdout (visible in Actions logs)
        print_summary(
            tier, changed_files, required_checks, blocked, violations, tier_rules
        )
        # Write machine-readable outputs to $GITHUB_OUTPUT
        write_github_outputs(
            {
                "tier": tier,
                "required_checks": json.dumps(required_checks),
                "blocked": str(blocked).lower(),
                "human_approval_required": str(human_approval_required).lower(),
                "changed_files_count": str(len(changed_files)),
            }
        )

    else:  # text
        print_summary(
            tier, changed_files, required_checks, blocked, violations, tier_rules
        )

    # ── Exit code ──────────────────────────────────────────────────────────────
    if blocked:
        print(
            f"Gate BLOCKED: {len(violations)} blocked pattern violation(s). "
            "See violations above.",
            file=sys.stderr,
        )
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
