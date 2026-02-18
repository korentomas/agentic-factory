"""
Tests for apps.orchestrator.jobs.pattern_extraction — pattern extraction job.

Covers:
- load_outcomes() JSONL parsing: valid files, empty files, malformed lines, defaults
- extract_patterns() positive pattern detection from clean outcomes
- extract_anti_patterns() negative pattern detection from failed outcomes
- analyze() full report generation: success rates, tier breakdowns, failure modes, costs
- format_rules_markdown() rendering reports as Markdown rules
- _split_patterns_markdown() splitting into patterns.md and anti-patterns.md
- _format_pr_list() PR number formatting
- run_extraction() end-to-end pipeline: file creation, missing outcomes handling
- _get_env() runtime env var reading
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from apps.orchestrator.jobs.pattern_extraction import (
    AgentOutcome,
    ExtractionReport,
    Pattern,
    _format_pr_list,
    _get_env,
    _split_patterns_markdown,
    analyze,
    extract_anti_patterns,
    extract_patterns,
    format_rules_markdown,
    load_outcomes,
    run_extraction,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _make_outcome(**kwargs: object) -> AgentOutcome:
    """Factory for creating test outcomes with sensible defaults."""
    defaults: dict[str, object] = {
        "outcome": "clean",
        "pr_url": "https://github.com/test/test/pull/1",
        "pr_number": 1,
        "branch": "agent/cu-gh-1",
        "risk_tier": "medium",
        "checks": {
            "gate": "success",
            "tests": "success",
            "review": "success",
            "spec_audit": "success",
        },
        "files_changed": ["apps/main.py"],
        "review_findings": [],
        "run_id": "123",
        "timestamp": "2026-02-18T00:00:00Z",
    }
    defaults.update(kwargs)
    return AgentOutcome(**defaults)  # type: ignore[arg-type]


def _outcome_to_dict(outcome: AgentOutcome) -> dict[str, object]:
    """Convert an AgentOutcome to a dict suitable for JSON serialization."""
    return {
        "outcome": outcome.outcome,
        "pr_url": outcome.pr_url,
        "pr_number": outcome.pr_number,
        "branch": outcome.branch,
        "risk_tier": outcome.risk_tier,
        "checks": outcome.checks,
        "files_changed": outcome.files_changed,
        "review_findings": outcome.review_findings,
        "run_id": outcome.run_id,
        "timestamp": outcome.timestamp,
        "cost_usd": outcome.cost_usd,
        "turns_total": outcome.turns_total,
    }


def _write_jsonl(path: Path, outcomes: list[AgentOutcome]) -> None:
    """Write a list of AgentOutcome objects as JSONL to the given path."""
    with open(path, "w") as f:
        for o in outcomes:
            f.write(json.dumps(_outcome_to_dict(o)) + "\n")


def _make_report(**kwargs: object) -> ExtractionReport:
    """Factory for creating test ExtractionReport with sensible defaults."""
    defaults: dict[str, object] = {
        "total_runs": 0,
        "success_rate": 0.0,
        "success_rate_by_tier": {},
        "common_failures": [],
        "file_hotspots": [],
        "patterns": [],
        "anti_patterns": [],
        "period_start": "",
        "period_end": "",
        "cost_by_outcome": {},
    }
    defaults.update(kwargs)
    return ExtractionReport(**defaults)  # type: ignore[arg-type]


# ── 1. TestLoadOutcomes ──────────────────────────────────────────────────────


class TestLoadOutcomes:
    """load_outcomes() JSONL file parsing and error handling."""

    def test_loads_valid_jsonl_file(self, tmp_path: Path) -> None:
        """Writes valid JSONL to tmp_path, loads correctly."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean"),
            _make_outcome(pr_number=2, outcome="tests-failed"),
            _make_outcome(pr_number=3, outcome="clean"),
        ]
        jsonl_path = tmp_path / "outcomes.jsonl"
        _write_jsonl(jsonl_path, outcomes)

        loaded = load_outcomes(str(jsonl_path))

        assert len(loaded) == 3
        assert loaded[0].pr_number == 1
        assert loaded[0].outcome == "clean"
        assert loaded[1].pr_number == 2
        assert loaded[1].outcome == "tests-failed"
        assert loaded[2].pr_number == 3

    def test_empty_file_returns_empty_list(self, tmp_path: Path) -> None:
        """Empty file returns []."""
        jsonl_path = tmp_path / "empty.jsonl"
        jsonl_path.write_text("")

        loaded = load_outcomes(str(jsonl_path))

        assert loaded == []

    def test_malformed_line_skipped(self, tmp_path: Path) -> None:
        """Mix of valid and invalid JSON; valid ones parsed, invalid skipped."""
        valid = _make_outcome(pr_number=10)
        jsonl_path = tmp_path / "mixed.jsonl"
        with open(jsonl_path, "w") as f:
            f.write(json.dumps(_outcome_to_dict(valid)) + "\n")
            f.write("this is not valid json\n")
            f.write("{broken json\n")
            valid2 = _make_outcome(pr_number=20)
            f.write(json.dumps(_outcome_to_dict(valid2)) + "\n")

        loaded = load_outcomes(str(jsonl_path))

        assert len(loaded) == 2
        assert loaded[0].pr_number == 10
        assert loaded[1].pr_number == 20

    def test_missing_required_field_skipped(self, tmp_path: Path) -> None:
        """Line missing a required field (e.g. 'outcome') is skipped."""
        data = {
            # "outcome" deliberately missing
            "pr_url": "https://github.com/test/test/pull/1",
            "pr_number": 1,
            "branch": "agent/cu-gh-1",
            "risk_tier": "low",
            "checks": {},
            "files_changed": [],
            "review_findings": [],
            "run_id": "abc",
            "timestamp": "2026-02-18T00:00:00Z",
        }
        jsonl_path = tmp_path / "missing.jsonl"
        jsonl_path.write_text(json.dumps(data) + "\n")

        loaded = load_outcomes(str(jsonl_path))

        assert loaded == []

    def test_missing_optional_fields_use_defaults(self, tmp_path: Path) -> None:
        """Outcome missing cost_usd and turns_total gets default values."""
        data = {
            "outcome": "clean",
            "pr_url": "https://github.com/test/test/pull/5",
            "pr_number": 5,
            "branch": "agent/cu-gh-5",
            "risk_tier": "low",
            "checks": {"gate": "success"},
            "files_changed": ["apps/foo.py"],
            "review_findings": [],
            "run_id": "abc",
            "timestamp": "2026-02-18T00:00:00Z",
        }
        jsonl_path = tmp_path / "defaults.jsonl"
        jsonl_path.write_text(json.dumps(data) + "\n")

        loaded = load_outcomes(str(jsonl_path))

        assert len(loaded) == 1
        assert loaded[0].cost_usd == 0.0
        assert loaded[0].turns_total == 0

    def test_file_not_found_returns_empty_list(self) -> None:
        """Nonexistent path returns []."""
        loaded = load_outcomes("/nonexistent/path/to/outcomes.jsonl")

        assert loaded == []

    def test_blank_lines_skipped(self, tmp_path: Path) -> None:
        """Blank lines in the file are silently skipped."""
        valid = _make_outcome(pr_number=1)
        jsonl_path = tmp_path / "blanks.jsonl"
        with open(jsonl_path, "w") as f:
            f.write("\n\n")
            f.write(json.dumps(_outcome_to_dict(valid)) + "\n")
            f.write("\n")

        loaded = load_outcomes(str(jsonl_path))

        assert len(loaded) == 1
        assert loaded[0].pr_number == 1

    def test_cost_usd_loaded_when_present(self, tmp_path: Path) -> None:
        """cost_usd is parsed from the data when present."""
        data = _outcome_to_dict(_make_outcome(pr_number=1))
        data["cost_usd"] = 1.25
        jsonl_path = tmp_path / "cost.jsonl"
        jsonl_path.write_text(json.dumps(data) + "\n")

        loaded = load_outcomes(str(jsonl_path))

        assert len(loaded) == 1
        assert loaded[0].cost_usd == 1.25


# ── 2. TestExtractPatterns ───────────────────────────────────────────────────


class TestExtractPatterns:
    """extract_patterns() positive pattern detection from clean outcomes."""

    def test_no_outcomes_returns_empty(self) -> None:
        """Empty list returns no patterns."""
        result = extract_patterns([])

        assert result == []

    def test_files_appearing_in_three_successes_become_pattern(self) -> None:
        """Same files in 3+ clean PRs produce a pattern."""
        outcomes = [
            _make_outcome(
                pr_number=1, outcome="clean", files_changed=["apps/api.py", "tests/test_api.py"]
            ),
            _make_outcome(
                pr_number=2, outcome="clean", files_changed=["apps/api.py", "apps/models.py"]
            ),
            _make_outcome(
                pr_number=3, outcome="clean", files_changed=["apps/api.py", "tests/test_api.py"]
            ),
        ]

        patterns = extract_patterns(outcomes, min_evidence=3)

        assert len(patterns) >= 1
        api_pattern = next(
            (p for p in patterns if "apps/api.py" in p.description), None
        )
        assert api_pattern is not None
        assert api_pattern.kind == "pattern"
        assert api_pattern.evidence_count == 3
        assert set(api_pattern.evidence_prs) == {1, 2, 3}

    def test_below_min_evidence_not_extracted(self) -> None:
        """2 occurrences with min_evidence=3 produces no pattern."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", files_changed=["apps/api.py"]),
            _make_outcome(pr_number=2, outcome="clean", files_changed=["apps/api.py"]),
        ]

        patterns = extract_patterns(outcomes, min_evidence=3)

        # No file-level patterns (only 2 occurrences), and directory-level
        # also only has 2 occurrences
        file_patterns = [p for p in patterns if "apps/api.py" in p.description]
        assert file_patterns == []

    def test_custom_min_evidence(self) -> None:
        """min_evidence=2 extracts pattern with 2 occurrences."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", files_changed=["apps/api.py"]),
            _make_outcome(pr_number=2, outcome="clean", files_changed=["apps/api.py"]),
        ]

        patterns = extract_patterns(outcomes, min_evidence=2)

        file_patterns = [p for p in patterns if "apps/api.py" in p.description]
        assert len(file_patterns) == 1
        assert file_patterns[0].evidence_count == 2

    def test_only_successful_outcomes_considered(self) -> None:
        """Failed PRs don't contribute to patterns."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", files_changed=["apps/api.py"]),
            _make_outcome(pr_number=2, outcome="tests-failed", files_changed=["apps/api.py"]),
            _make_outcome(pr_number=3, outcome="clean", files_changed=["apps/api.py"]),
            _make_outcome(pr_number=4, outcome="review-failed", files_changed=["apps/api.py"]),
            _make_outcome(pr_number=5, outcome="clean", files_changed=["apps/api.py"]),
        ]

        patterns = extract_patterns(outcomes, min_evidence=3)

        # Only PRs 1, 3, 5 are clean — exactly 3 occurrences
        file_patterns = [p for p in patterns if "apps/api.py" in p.description]
        assert len(file_patterns) == 1
        assert file_patterns[0].evidence_count == 3
        assert set(file_patterns[0].evidence_prs) == {1, 3, 5}

    def test_directory_level_patterns_extracted(self) -> None:
        """Directories with 3+ successful PRs produce a directory-level pattern."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", files_changed=["apps/routers/a.py"]),
            _make_outcome(pr_number=2, outcome="clean", files_changed=["apps/routers/b.py"]),
            _make_outcome(pr_number=3, outcome="clean", files_changed=["apps/routers/c.py"]),
        ]

        patterns = extract_patterns(outcomes, min_evidence=3)

        dir_patterns = [p for p in patterns if "apps/routers/" in p.description]
        assert len(dir_patterns) == 1
        assert dir_patterns[0].evidence_count == 3

    def test_confidence_capped_at_one(self) -> None:
        """Confidence never exceeds 1.0 even when count equals total."""
        outcomes = [
            _make_outcome(pr_number=i, outcome="clean", files_changed=["apps/x.py"])
            for i in range(1, 4)
        ]

        patterns = extract_patterns(outcomes, min_evidence=3)

        for p in patterns:
            assert p.confidence <= 1.0


# ── 3. TestExtractAntiPatterns ───────────────────────────────────────────────


class TestExtractAntiPatterns:
    """extract_anti_patterns() negative pattern detection from failed outcomes."""

    def test_no_failures_returns_empty(self) -> None:
        """All clean outcomes produce no anti-patterns."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean"),
            _make_outcome(pr_number=2, outcome="clean"),
            _make_outcome(pr_number=3, outcome="clean"),
        ]

        anti_patterns = extract_anti_patterns(outcomes)

        assert anti_patterns == []

    def test_repeated_check_failure_becomes_anti_pattern(self) -> None:
        """A check failing 2+ times produces an anti-pattern."""
        outcomes = [
            _make_outcome(
                pr_number=1,
                outcome="tests-failed",
                checks={"tests": "failure", "review": "skipped"},
                files_changed=["a.py"],
            ),
            _make_outcome(
                pr_number=2,
                outcome="tests-failed",
                checks={"tests": "failure", "review": "skipped"},
                files_changed=["b.py"],
            ),
            _make_outcome(pr_number=3, outcome="clean"),
        ]

        anti_patterns = extract_anti_patterns(outcomes, min_evidence=2)

        check_ap = next(
            (ap for ap in anti_patterns if "`tests`" in ap.description), None
        )
        assert check_ap is not None
        assert check_ap.kind == "anti-pattern"
        assert check_ap.evidence_count == 2
        assert set(check_ap.evidence_prs) == {1, 2}

    def test_check_failure_includes_file_hints(self) -> None:
        """Anti-pattern for a failing check mentions involved files."""
        outcomes = [
            _make_outcome(
                pr_number=1,
                outcome="tests-failed",
                checks={"tests": "failure"},
                files_changed=["apps/fragile.py"],
            ),
            _make_outcome(
                pr_number=2,
                outcome="tests-failed",
                checks={"tests": "failure"},
                files_changed=["apps/fragile.py"],
            ),
        ]

        anti_patterns = extract_anti_patterns(outcomes, min_evidence=2)

        check_ap = next(
            (ap for ap in anti_patterns if "`tests`" in ap.description), None
        )
        assert check_ap is not None
        assert "apps/fragile.py" in check_ap.description

    def test_single_failure_not_extracted(self) -> None:
        """1 check failure below min_evidence produces no anti-pattern."""
        outcomes = [
            _make_outcome(
                pr_number=1,
                outcome="tests-failed",
                checks={"tests": "failure"},
                files_changed=["a.py"],
            ),
            _make_outcome(pr_number=2, outcome="clean"),
        ]

        anti_patterns = extract_anti_patterns(outcomes, min_evidence=2)

        check_aps = [ap for ap in anti_patterns if "`tests`" in ap.description]
        assert check_aps == []

    def test_file_hotspots_in_failed_prs(self) -> None:
        """Files appearing in multiple failed PRs are noted as anti-patterns."""
        outcomes = [
            _make_outcome(
                pr_number=1,
                outcome="tests-failed",
                checks={"tests": "failure"},
                files_changed=["apps/fragile.py"],
            ),
            _make_outcome(
                pr_number=2,
                outcome="review-failed",
                checks={"review": "failure"},
                files_changed=["apps/fragile.py"],
            ),
            _make_outcome(pr_number=3, outcome="clean", files_changed=["apps/stable.py"]),
        ]

        anti_patterns = extract_anti_patterns(outcomes, min_evidence=2)

        hotspot_ap = next(
            (ap for ap in anti_patterns if "apps/fragile.py" in ap.description
             and "failed PRs" in ap.description), None
        )
        assert hotspot_ap is not None
        assert hotspot_ap.evidence_count == 2
        assert set(hotspot_ap.evidence_prs) == {1, 2}

    def test_empty_outcomes_returns_empty(self) -> None:
        """Empty input returns no anti-patterns."""
        assert extract_anti_patterns([]) == []


# ── 4. TestAnalyze ───────────────────────────────────────────────────────────


class TestAnalyze:
    """analyze() full report generation."""

    def test_basic_analysis(self) -> None:
        """Mix of outcomes produces correct report with all fields populated."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", risk_tier="low"),
            _make_outcome(
                pr_number=2,
                outcome="tests-failed",
                risk_tier="medium",
                checks={"tests": "failure"},
            ),
            _make_outcome(pr_number=3, outcome="clean", risk_tier="medium"),
            _make_outcome(pr_number=4, outcome="clean", risk_tier="high"),
        ]

        report = analyze(outcomes)

        assert report.total_runs == 4
        # 3 clean out of 4 = 0.75
        assert report.success_rate == 0.75
        assert report.period_start != ""
        assert report.period_end != ""

    def test_success_rate_as_fraction(self) -> None:
        """3 clean + 1 failed = 0.75 success rate (fraction, not percentage)."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean"),
            _make_outcome(pr_number=2, outcome="clean"),
            _make_outcome(pr_number=3, outcome="clean"),
            _make_outcome(
                pr_number=4, outcome="tests-failed", checks={"tests": "failure"}
            ),
        ]

        report = analyze(outcomes)

        assert report.success_rate == 0.75

    def test_success_rate_by_tier(self) -> None:
        """Separate success rates for low/medium/high tiers (as fractions)."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", risk_tier="low"),
            _make_outcome(pr_number=2, outcome="clean", risk_tier="low"),
            _make_outcome(
                pr_number=3,
                outcome="tests-failed",
                risk_tier="medium",
                checks={"tests": "failure"},
            ),
            _make_outcome(pr_number=4, outcome="clean", risk_tier="medium"),
            _make_outcome(
                pr_number=5,
                outcome="tests-failed",
                risk_tier="high",
                checks={"tests": "failure"},
            ),
        ]

        report = analyze(outcomes)

        assert report.success_rate_by_tier["low"] == 1.0
        assert report.success_rate_by_tier["medium"] == 0.5
        assert report.success_rate_by_tier["high"] == 0.0

    def test_common_failures_are_check_level(self) -> None:
        """common_failures tracks which checks fail, not outcome types."""
        outcomes = [
            _make_outcome(
                pr_number=1,
                outcome="tests-failed",
                checks={"tests": "failure", "review": "skipped"},
            ),
            _make_outcome(
                pr_number=2,
                outcome="tests-failed",
                checks={"tests": "failure", "review": "skipped"},
            ),
            _make_outcome(
                pr_number=3,
                outcome="review-failed",
                checks={"tests": "success", "review": "failure"},
            ),
        ]

        report = analyze(outcomes)

        failure_dict = dict(report.common_failures)
        assert failure_dict["tests"] == 2
        assert failure_dict["review"] == 1

    def test_empty_outcomes(self) -> None:
        """Empty list produces zero-count report."""
        report = analyze([])

        assert report.total_runs == 0
        assert report.success_rate == 0.0
        assert report.success_rate_by_tier == {}
        assert report.common_failures == []
        assert report.file_hotspots == []
        assert report.patterns == []
        assert report.anti_patterns == []
        assert report.period_start == ""
        assert report.period_end == ""
        assert report.cost_by_outcome == {}

    def test_cost_by_outcome_computed(self) -> None:
        """Average cost per outcome type is computed from outcomes with cost_usd > 0."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", cost_usd=1.0),
            _make_outcome(pr_number=2, outcome="clean", cost_usd=3.0),
            _make_outcome(
                pr_number=3,
                outcome="tests-failed",
                cost_usd=2.0,
                checks={"tests": "failure"},
            ),
        ]

        report = analyze(outcomes)

        # Average clean cost: (1.0 + 3.0) / 2 = 2.0
        assert report.cost_by_outcome["clean"] == 2.0
        # Average tests-failed cost: 2.0 / 1 = 2.0
        assert report.cost_by_outcome["tests-failed"] == 2.0

    def test_cost_by_outcome_excludes_zero_cost(self) -> None:
        """Outcomes with cost_usd=0.0 do not contribute to cost averages."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", cost_usd=0.0),
            _make_outcome(pr_number=2, outcome="clean", cost_usd=4.0),
        ]

        report = analyze(outcomes)

        # Only PR 2 has cost > 0, so average is 4.0 / 1 = 4.0
        assert report.cost_by_outcome["clean"] == 4.0

    def test_file_hotspots_only_from_failed_prs(self) -> None:
        """file_hotspots only counts files from non-clean outcomes."""
        outcomes = [
            _make_outcome(pr_number=1, outcome="clean", files_changed=["good.py"]),
            _make_outcome(
                pr_number=2,
                outcome="tests-failed",
                files_changed=["bad.py"],
                checks={"tests": "failure"},
            ),
        ]

        report = analyze(outcomes)

        hotspot_files = [f for f, _ in report.file_hotspots]
        assert "bad.py" in hotspot_files
        assert "good.py" not in hotspot_files

    def test_period_start_and_end(self) -> None:
        """period_start is the earliest timestamp, period_end the latest."""
        outcomes = [
            _make_outcome(pr_number=1, timestamp="2026-02-10T00:00:00Z"),
            _make_outcome(pr_number=2, timestamp="2026-02-15T00:00:00Z"),
            _make_outcome(pr_number=3, timestamp="2026-02-01T00:00:00Z"),
        ]

        report = analyze(outcomes)

        assert report.period_start == "2026-02-01T00:00:00Z"
        assert report.period_end == "2026-02-15T00:00:00Z"


# ── 5. TestFormatPrList ──────────────────────────────────────────────────────


class TestFormatPrList:
    """_format_pr_list() PR number formatting."""

    def test_single_pr(self) -> None:
        assert _format_pr_list([5]) == "#5"

    def test_two_prs(self) -> None:
        assert _format_pr_list([5, 10]) == "#5, #10"

    def test_three_prs(self) -> None:
        assert _format_pr_list([1, 2, 3]) == "#1, #2, #3"

    def test_more_than_three_prs_truncated(self) -> None:
        result = _format_pr_list([1, 2, 3, 4, 5])
        assert result == "#1, #2, #3 +2 more"

    def test_duplicates_deduplicated(self) -> None:
        result = _format_pr_list([1, 1, 2, 2, 3])
        assert result == "#1, #2, #3"

    def test_unsorted_prs_sorted(self) -> None:
        result = _format_pr_list([5, 1, 3])
        assert result == "#1, #3, #5"


# ── 6. TestFormatRulesMarkdown ───────────────────────────────────────────────


class TestFormatRulesMarkdown:
    """format_rules_markdown() rendering reports as Markdown rules."""

    def test_zero_runs_produces_empty_state(self) -> None:
        """Zero runs produces a simple 'no data' message."""
        report = _make_report(total_runs=0)

        markdown = format_rules_markdown(report)

        assert "No agent outcomes recorded yet." in markdown

    def test_includes_success_rate_as_percentage(self) -> None:
        """Success rate fraction is formatted as percentage in markdown."""
        report = _make_report(
            total_runs=10,
            success_rate=0.8,
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        assert "80%" in markdown

    def test_includes_tier_success_rates(self) -> None:
        """Success rate by tier is rendered."""
        report = _make_report(
            total_runs=10,
            success_rate=0.7,
            success_rate_by_tier={"low": 1.0, "medium": 0.5, "high": 0.0},
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        assert "low: 100%" in markdown
        assert "medium: 50%" in markdown
        assert "high: 0%" in markdown

    def test_includes_patterns(self) -> None:
        """Each pattern appears in output under 'What Works Well'."""
        patterns = [
            Pattern(
                kind="pattern",
                description="File `apps/api.py` has been successfully modified in 5 clean PRs.",
                evidence_count=5,
                evidence_prs=[1, 2, 3, 4, 5],
                confidence=0.8,
            ),
        ]
        report = _make_report(
            total_runs=10,
            success_rate=0.5,
            patterns=patterns,
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        assert "apps/api.py" in markdown
        assert "What Works Well" in markdown

    def test_includes_anti_patterns(self) -> None:
        """Each anti-pattern appears in output under 'Watch Out For'."""
        anti_patterns = [
            Pattern(
                kind="anti-pattern",
                description="The `tests` check has failed in 4 PRs.",
                evidence_count=4,
                evidence_prs=[2, 4, 6, 8],
                confidence=0.75,
            ),
        ]
        report = _make_report(
            total_runs=10,
            success_rate=0.5,
            anti_patterns=anti_patterns,
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        assert "tests" in markdown
        assert "Watch Out For" in markdown

    def test_includes_common_failures(self) -> None:
        """Common failures section appears when failures exist."""
        report = _make_report(
            total_runs=5,
            success_rate=0.6,
            common_failures=[("tests", 3), ("review", 1)],
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        assert "Common Failure Checks" in markdown
        assert "`tests`: failed 3 time(s)" in markdown

    def test_includes_file_hotspots(self) -> None:
        """File hotspots section appears when hotspots exist."""
        report = _make_report(
            total_runs=5,
            success_rate=0.6,
            file_hotspots=[("apps/fragile.py", 3)],
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        assert "File Hotspots" in markdown
        assert "`apps/fragile.py`" in markdown

    def test_includes_cost_trends(self) -> None:
        """Cost trends section appears when cost data exists."""
        report = _make_report(
            total_runs=5,
            success_rate=0.8,
            cost_by_outcome={"clean": 1.5, "tests-failed": 2.0},
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        assert "Cost Trends" in markdown
        assert "$1.5000" in markdown
        assert "$2.0000" in markdown

    def test_patterns_limited_to_five(self) -> None:
        """At most 5 patterns are rendered."""
        patterns = [
            Pattern(
                kind="pattern",
                description=f"Pattern {i}",
                evidence_count=10 - i,
                evidence_prs=[i],
                confidence=0.5,
            )
            for i in range(10)
        ]
        report = _make_report(
            total_runs=20,
            success_rate=0.5,
            patterns=patterns,
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        markdown = format_rules_markdown(report)

        # Only first 5 should appear
        assert "Pattern 0" in markdown
        assert "Pattern 4" in markdown
        assert "Pattern 5" not in markdown


# ── 7. TestSplitPatternsMarkdown ─────────────────────────────────────────────


class TestSplitPatternsMarkdown:
    """_split_patterns_markdown() splitting into patterns and anti-patterns files."""

    def test_zero_runs_produces_empty_state_for_both(self) -> None:
        """Zero runs produces 'no data' in both files."""
        report = _make_report(total_runs=0)

        pat_md, anti_md = _split_patterns_markdown(report)

        assert "No agent outcomes recorded yet." in pat_md
        assert "No agent outcomes recorded yet." in anti_md

    def test_patterns_file_contains_patterns(self) -> None:
        """Patterns file contains patterns but not anti-patterns."""
        patterns = [
            Pattern(
                kind="pattern",
                description="Test pattern",
                evidence_count=3,
                evidence_prs=[1, 2, 3],
                confidence=0.5,
            ),
        ]
        anti_patterns = [
            Pattern(
                kind="anti-pattern",
                description="Test anti-pattern",
                evidence_count=2,
                evidence_prs=[4, 5],
                confidence=0.5,
            ),
        ]
        report = _make_report(
            total_runs=5,
            success_rate=0.6,
            patterns=patterns,
            anti_patterns=anti_patterns,
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        pat_md, anti_md = _split_patterns_markdown(report)

        assert "Test pattern" in pat_md
        assert "Test anti-pattern" not in pat_md
        assert "Test anti-pattern" in anti_md

    def test_anti_patterns_file_has_hotspot_advice(self) -> None:
        """Anti-patterns file includes actionable advice for hotspot files."""
        report = _make_report(
            total_runs=5,
            success_rate=0.6,
            file_hotspots=[("apps/fragile.py", 3)],
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        _, anti_md = _split_patterns_markdown(report)

        assert "run tests early" in anti_md

    def test_no_anti_patterns_produces_placeholder(self) -> None:
        """When no anti-patterns detected, a placeholder message is shown."""
        report = _make_report(
            total_runs=5,
            success_rate=1.0,
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        _, anti_md = _split_patterns_markdown(report)

        assert "No recurring anti-patterns detected yet." in anti_md

    def test_patterns_file_has_cost_section(self) -> None:
        """Patterns file includes cost-per-outcome section when data exists."""
        report = _make_report(
            total_runs=5,
            success_rate=0.8,
            cost_by_outcome={"clean": 1.5},
            period_start="2026-02-01",
            period_end="2026-02-18",
        )

        pat_md, _ = _split_patterns_markdown(report)

        assert "Cost per Outcome" in pat_md
        assert "$1.5000" in pat_md


# ── 8. TestRunExtraction ─────────────────────────────────────────────────────


class TestRunExtraction:
    """run_extraction() end-to-end pipeline."""

    async def test_run_extraction_writes_two_rules_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Creates both patterns.md and anti-patterns.md from outcomes."""
        outcomes = [
            _make_outcome(pr_number=i, outcome="clean", files_changed=["apps/api.py"])
            for i in range(1, 6)
        ]
        outcomes.append(
            _make_outcome(
                pr_number=6,
                outcome="tests-failed",
                files_changed=["apps/broken.py"],
                checks={"tests": "failure"},
            )
        )
        jsonl_path = tmp_path / "outcomes.jsonl"
        _write_jsonl(jsonl_path, outcomes)

        monkeypatch.setenv("OUTCOMES_PATH", str(jsonl_path))
        monkeypatch.setenv("RULES_DIR", str(tmp_path / ".claude" / "rules"))

        exit_code = await run_extraction()

        assert exit_code == 0

        patterns_path = tmp_path / ".claude" / "rules" / "patterns.md"
        assert patterns_path.exists()
        pat_content = patterns_path.read_text()
        assert "What Works Well" in pat_content

        anti_path = tmp_path / ".claude" / "rules" / "anti-patterns.md"
        assert anti_path.exists()

    async def test_run_extraction_no_outcomes_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Handles missing JSONL file gracefully — still writes empty-state files."""
        monkeypatch.setenv("OUTCOMES_PATH", str(tmp_path / "nonexistent.jsonl"))
        monkeypatch.setenv("RULES_DIR", str(tmp_path / ".claude" / "rules"))

        exit_code = await run_extraction()

        assert exit_code == 0

        # Empty-state files should still be written
        patterns_path = tmp_path / ".claude" / "rules" / "patterns.md"
        assert patterns_path.exists()
        content = patterns_path.read_text()
        assert "No agent outcomes recorded yet." in content

    async def test_run_extraction_creates_rules_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Creates .claude/rules/ directory if it doesn't exist."""
        rules_dir = tmp_path / "new-project" / ".claude" / "rules"
        assert not rules_dir.exists()

        jsonl_path = tmp_path / "outcomes.jsonl"
        _write_jsonl(jsonl_path, [_make_outcome(pr_number=1)])

        monkeypatch.setenv("OUTCOMES_PATH", str(jsonl_path))
        monkeypatch.setenv("RULES_DIR", str(rules_dir))

        exit_code = await run_extraction()

        assert exit_code == 0
        assert rules_dir.exists()

    async def test_run_extraction_returns_zero_for_empty_outcomes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Empty JSONL file still succeeds with exit code 0."""
        jsonl_path = tmp_path / "empty.jsonl"
        jsonl_path.write_text("")

        monkeypatch.setenv("OUTCOMES_PATH", str(jsonl_path))
        monkeypatch.setenv("RULES_DIR", str(tmp_path / ".claude" / "rules"))

        exit_code = await run_extraction()

        assert exit_code == 0


# ── 9. TestGetEnv ────────────────────────────────────────────────────────────


class TestGetEnv:
    """_get_env reads env vars at call time, not import time."""

    def test_reads_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TEST_PE_KEY", "test_value")
        assert _get_env("TEST_PE_KEY") == "test_value"

    def test_returns_default_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("TEST_PE_KEY", raising=False)
        assert _get_env("TEST_PE_KEY", "fallback") == "fallback"

    def test_returns_empty_string_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NONEXISTENT_PE_KEY_12345", raising=False)
        assert _get_env("NONEXISTENT_PE_KEY_12345") == ""
