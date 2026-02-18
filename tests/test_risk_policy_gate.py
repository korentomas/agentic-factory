"""
Tests for scripts/risk_policy_gate.py — the risk policy gate.

Tests cover:
- match_glob: fnmatch, directory, double-star, and basename patterns
- parse_changed_files: various delimiters and edge cases
- determine_tier: tier escalation logic
- check_blocked_patterns: violation detection
- load_policy: valid and invalid policy files
- write_github_outputs: GitHub Actions output writing
- print_summary: smoke test to verify no crashes
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.risk_policy_gate import (
    check_blocked_patterns,
    determine_tier,
    load_policy,
    match_glob,
    parse_changed_files,
    print_summary,
    write_github_outputs,
)

# ─── match_glob: standard fnmatch patterns ──────────────────────────────────


class TestMatchGlobStandardPatterns:
    """Standard fnmatch-style patterns like *.py and *.md."""

    def test_star_dot_py_matches_python_file_in_root(self) -> None:
        assert match_glob("setup.py", "*.py") is True

    def test_star_dot_py_matches_python_file_in_subdirectory(self) -> None:
        assert match_glob("apps/api/main.py", "*.py") is True

    def test_star_dot_md_matches_markdown_file_in_root(self) -> None:
        assert match_glob("README.md", "*.md") is True

    def test_star_dot_md_matches_markdown_file_in_subdirectory(self) -> None:
        assert match_glob("docs/guide.md", "*.md") is True

    def test_star_dot_py_does_not_match_non_python_file(self) -> None:
        assert match_glob("config.json", "*.py") is False

    def test_exact_filename_pattern_matches(self) -> None:
        assert match_glob("LICENSE", "LICENSE") is True

    def test_exact_filename_pattern_does_not_match_different_file(self) -> None:
        assert match_glob("CHANGELOG", "LICENSE") is False

    def test_star_dot_txt_matches_text_file_in_subdirectory(self) -> None:
        assert match_glob("notes/todo.txt", "*.txt") is True


# ─── match_glob: directory patterns ──────────────────────────────────────────


class TestMatchGlobDirectoryPatterns:
    """Directory patterns like apps/auth/**."""

    def test_directory_doublestar_matches_file_inside(self) -> None:
        assert match_glob("apps/auth/jwt.py", "apps/auth/**") is True

    def test_directory_doublestar_matches_nested_file(self) -> None:
        assert match_glob("apps/auth/utils/tokens.py", "apps/auth/**") is True

    def test_directory_doublestar_does_not_match_sibling_directory(self) -> None:
        assert match_glob("apps/api/main.py", "apps/auth/**") is False

    def test_github_workflows_doublestar_matches_workflow_file(self) -> None:
        assert match_glob(".github/workflows/ci.yml", ".github/workflows/**") is True

    def test_claude_hooks_doublestar_matches_hook_file(self) -> None:
        assert match_glob(".claude/hooks/pre-commit.sh", ".claude/hooks/**") is True

    def test_tests_doublestar_matches_test_file(self) -> None:
        assert match_glob("tests/test_gate.py", "tests/**") is True

    def test_tests_doublestar_matches_deeply_nested_test(self) -> None:
        assert match_glob("tests/unit/api/test_auth.py", "tests/**") is True

    def test_docs_doublestar_matches_docs_file(self) -> None:
        assert match_glob("docs/architecture.md", "docs/**") is True


# ─── match_glob: double-star recursive matching ─────────────────────────────


class TestMatchGlobDoubleStarRecursive:
    """Double-star patterns like apps/**/models.py."""

    def test_doublestar_in_middle_matches_intermediate_directory(self) -> None:
        assert match_glob("apps/orchestrator/models.py", "apps/**/models.py") is True

    def test_doublestar_in_middle_matches_deeply_nested(self) -> None:
        assert (
            match_glob("apps/api/v2/db/models.py", "apps/**/models.py") is True
        )

    def test_doublestar_in_middle_does_not_match_wrong_filename(self) -> None:
        assert match_glob("apps/orchestrator/views.py", "apps/**/models.py") is False

    def test_doublestar_md_matches_markdown_anywhere(self) -> None:
        assert match_glob("deep/nested/path/README.md", "**/*.md") is True

    def test_doublestar_md_matches_root_markdown(self) -> None:
        assert match_glob("README.md", "**/*.md") is True

    def test_jobs_doublestar_matches_jobs_subfile(self) -> None:
        assert (
            match_glob("apps/orchestrator/jobs/deploy.py", "apps/orchestrator/jobs/**")
            is True
        )


# ─── match_glob: basename-only patterns ─────────────────────────────────────


class TestMatchGlobBasenameOnly:
    """Basename-only patterns like *.sql matching path/to/file.sql."""

    def test_star_sql_matches_sql_file_in_subdirectory(self) -> None:
        assert match_glob("path/to/migration.sql", "*.sql") is True

    def test_star_sql_matches_sql_file_in_root(self) -> None:
        assert match_glob("schema.sql", "*.sql") is True

    def test_star_sql_does_not_match_non_sql_file(self) -> None:
        assert match_glob("path/to/data.json", "*.sql") is False

    def test_basename_exact_match_env_example(self) -> None:
        assert match_glob(".env.example", ".env.example") is True

    def test_star_cypher_matches_cypher_file_in_subdirectory(self) -> None:
        assert match_glob("queries/search.cypher", "*.cypher") is True

    def test_backslash_path_separators_are_normalized(self) -> None:
        assert match_glob("apps\\api\\main.py", "*.py") is True


# ─── parse_changed_files ─────────────────────────────────────────────────────


class TestParseChangedFiles:
    """Parsing the --changed-files argument with various formats."""

    def test_space_separated_files(self) -> None:
        result = parse_changed_files("file1.py file2.py file3.py")
        assert result == ["file1.py", "file2.py", "file3.py"]

    def test_newline_separated_files(self) -> None:
        result = parse_changed_files("file1.py\nfile2.py\nfile3.py")
        assert result == ["file1.py", "file2.py", "file3.py"]

    def test_mixed_separators(self) -> None:
        result = parse_changed_files("file1.py\nfile2.py file3.py\nfile4.py")
        assert result == ["file1.py", "file2.py", "file3.py", "file4.py"]

    def test_empty_string_returns_empty_list(self) -> None:
        result = parse_changed_files("")
        assert result == []

    def test_whitespace_only_returns_empty_list(self) -> None:
        result = parse_changed_files("   \n  \n  ")
        assert result == []

    def test_leading_and_trailing_whitespace_stripped(self) -> None:
        result = parse_changed_files("  file1.py  \n  file2.py  ")
        assert result == ["file1.py", "file2.py"]

    def test_carriage_return_newline_separated(self) -> None:
        result = parse_changed_files("file1.py\r\nfile2.py\r\nfile3.py")
        assert result == ["file1.py", "file2.py", "file3.py"]

    def test_multiple_consecutive_spaces_handled(self) -> None:
        result = parse_changed_files("file1.py   file2.py")
        assert result == ["file1.py", "file2.py"]

    def test_single_file(self) -> None:
        result = parse_changed_files("only_one.py")
        assert result == ["only_one.py"]

    def test_paths_with_directories(self) -> None:
        result = parse_changed_files("apps/api/main.py apps/auth/jwt.py")
        assert result == ["apps/api/main.py", "apps/auth/jwt.py"]


# ─── determine_tier ──────────────────────────────────────────────────────────


class TestDetermineTier:
    """Tier determination based on changed files and tier rules."""

    @pytest.fixture()
    def tier_rules(self) -> dict[str, list[str]]:
        return {
            "high": [
                ".github/workflows/**",
                "scripts/risk_policy_gate.py",
                ".claude/hooks/**",
            ],
            "medium": [
                "apps/orchestrator/models.py",
                "apps/orchestrator/jobs/**",
            ],
            "low": [
                "docs/**",
                "*.md",
                "tests/**",
            ],
        }

    def test_single_high_risk_file_returns_high(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = [".github/workflows/ci.yml"]
        assert determine_tier(files, tier_rules) == "high"

    def test_single_medium_risk_file_returns_medium(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["apps/orchestrator/models.py"]
        assert determine_tier(files, tier_rules) == "medium"

    def test_single_low_risk_file_returns_low(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["docs/guide.md"]
        assert determine_tier(files, tier_rules) == "low"

    def test_mixed_files_highest_tier_wins_high_over_low(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["docs/guide.md", ".github/workflows/deploy.yml"]
        assert determine_tier(files, tier_rules) == "high"

    def test_mixed_files_highest_tier_wins_medium_over_low(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["tests/test_something.py", "apps/orchestrator/models.py"]
        assert determine_tier(files, tier_rules) == "medium"

    def test_mixed_files_highest_tier_wins_high_over_medium(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["apps/orchestrator/jobs/deploy.py", "scripts/risk_policy_gate.py"]
        assert determine_tier(files, tier_rules) == "high"

    def test_all_three_tiers_present_returns_high(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = [
            "README.md",
            "apps/orchestrator/models.py",
            ".github/workflows/ci.yml",
        ]
        assert determine_tier(files, tier_rules) == "high"

    def test_only_low_risk_files_returns_low(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["docs/setup.md", "tests/test_api.py", "README.md"]
        assert determine_tier(files, tier_rules) == "low"

    def test_no_matching_patterns_defaults_to_low(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["some/unknown/file.xyz", "another/random.bin"]
        assert determine_tier(files, tier_rules) == "low"

    def test_empty_file_list_returns_low(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        assert determine_tier([], tier_rules) == "low"

    def test_empty_tier_rules_returns_low(self) -> None:
        files = [".github/workflows/ci.yml"]
        assert determine_tier(files, {}) == "low"

    def test_exact_filename_match_in_high_tier(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = ["scripts/risk_policy_gate.py"]
        assert determine_tier(files, tier_rules) == "high"

    def test_multiple_high_risk_files_still_returns_high(
        self, tier_rules: dict[str, list[str]]
    ) -> None:
        files = [
            ".github/workflows/ci.yml",
            ".github/workflows/deploy.yml",
            "scripts/risk_policy_gate.py",
        ]
        assert determine_tier(files, tier_rules) == "high"


# ─── check_blocked_patterns ──────────────────────────────────────────────────


class TestCheckBlockedPatterns:
    """Blocked pattern detection."""

    def test_matching_file_returns_violation(self) -> None:
        blocked = [
            {"pattern": "*.env", "reason": "Env files must not be committed"},
        ]
        files = ["production.env"]
        violations = check_blocked_patterns(files, blocked)
        assert len(violations) == 1
        assert violations[0]["file"] == "production.env"
        assert violations[0]["pattern"] == "*.env"
        assert violations[0]["reason"] == "Env files must not be committed"

    def test_no_matching_file_returns_empty_list(self) -> None:
        blocked = [
            {"pattern": "*.env", "reason": "Env files must not be committed"},
        ]
        files = ["apps/main.py", "README.md"]
        violations = check_blocked_patterns(files, blocked)
        assert violations == []

    def test_multiple_violations_for_multiple_matching_files(self) -> None:
        blocked = [
            {"pattern": "*.env", "reason": "Env files blocked"},
        ]
        files = ["staging.env", "production.env"]
        violations = check_blocked_patterns(files, blocked)
        assert len(violations) == 2

    def test_multiple_blocked_patterns_each_checked(self) -> None:
        blocked = [
            {"pattern": "*.env", "reason": "Env files blocked"},
            {"pattern": "*.secret", "reason": "Secret files blocked"},
        ]
        files = ["staging.env", "api.secret"]
        violations = check_blocked_patterns(files, blocked)
        assert len(violations) == 2
        patterns_found = {v["pattern"] for v in violations}
        assert patterns_found == {"*.env", "*.secret"}

    def test_empty_blocked_patterns_returns_empty_list(self) -> None:
        violations = check_blocked_patterns(["any/file.py"], [])
        assert violations == []

    def test_empty_files_returns_empty_list(self) -> None:
        blocked = [{"pattern": "*.env", "reason": "blocked"}]
        violations = check_blocked_patterns([], blocked)
        assert violations == []

    def test_pattern_with_directory_glob(self) -> None:
        blocked = [
            {"pattern": "secrets/**", "reason": "Secrets directory blocked"},
        ]
        files = ["secrets/aws_keys.json"]
        violations = check_blocked_patterns(files, blocked)
        assert len(violations) == 1
        assert violations[0]["file"] == "secrets/aws_keys.json"

    def test_entry_with_empty_pattern_is_skipped(self) -> None:
        blocked = [
            {"pattern": "", "reason": "Should be skipped"},
        ]
        files = ["anything.py"]
        violations = check_blocked_patterns(files, blocked)
        assert violations == []

    def test_entry_without_pattern_key_is_skipped(self) -> None:
        blocked = [
            {"reason": "No pattern key present"},
        ]
        files = ["anything.py"]
        violations = check_blocked_patterns(files, blocked)
        assert violations == []

    def test_violation_includes_tier_from_entry(self) -> None:
        blocked = [
            {"pattern": "*.env", "reason": "Blocked", "tier": "critical"},
        ]
        files = ["app.env"]
        violations = check_blocked_patterns(files, blocked)
        assert violations[0]["tier"] == "critical"

    def test_violation_uses_default_tier_when_not_specified(self) -> None:
        blocked = [
            {"pattern": "*.env", "reason": "Blocked"},
        ]
        files = ["app.env"]
        violations = check_blocked_patterns(files, blocked)
        assert violations[0]["tier"] == "high"


# ─── load_policy ─────────────────────────────────────────────────────────────


class TestLoadPolicy:
    """Loading and validating the risk policy JSON file."""

    def test_valid_policy_loads_successfully(self, tmp_path: Path) -> None:
        policy_data = {
            "riskTierRules": {"high": ["*.py"], "low": ["*.md"]},
            "mergePolicy": {"high": {"requiredChecks": ["tests"]}},
        }
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(json.dumps(policy_data))

        result = load_policy(str(policy_file))
        assert result == policy_data

    def test_missing_file_exits_with_code_1(self, tmp_path: Path) -> None:
        missing_path = str(tmp_path / "nonexistent.json")
        with pytest.raises(SystemExit) as exc_info:
            load_policy(missing_path)
        assert exc_info.value.code == 1

    def test_invalid_json_exits_with_code_1(self, tmp_path: Path) -> None:
        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{not valid json!!")
        with pytest.raises(SystemExit) as exc_info:
            load_policy(str(bad_file))
        assert exc_info.value.code == 1

    def test_missing_risk_tier_rules_key_exits_with_code_1(
        self, tmp_path: Path
    ) -> None:
        policy_data = {"mergePolicy": {"low": {}}}
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(json.dumps(policy_data))
        with pytest.raises(SystemExit) as exc_info:
            load_policy(str(policy_file))
        assert exc_info.value.code == 1

    def test_missing_merge_policy_key_exits_with_code_1(
        self, tmp_path: Path
    ) -> None:
        policy_data = {"riskTierRules": {"high": ["*.py"]}}
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(json.dumps(policy_data))
        with pytest.raises(SystemExit) as exc_info:
            load_policy(str(policy_file))
        assert exc_info.value.code == 1

    def test_policy_with_extra_keys_loads_fine(self, tmp_path: Path) -> None:
        policy_data = {
            "riskTierRules": {"low": ["*.md"]},
            "mergePolicy": {"low": {}},
            "extraStuff": True,
            "version": "1",
        }
        policy_file = tmp_path / "policy.json"
        policy_file.write_text(json.dumps(policy_data))

        result = load_policy(str(policy_file))
        assert "extraStuff" in result


# ─── write_github_outputs ────────────────────────────────────────────────────


class TestWriteGithubOutputs:
    """Writing step outputs for GitHub Actions."""

    def test_writes_key_value_pairs_to_github_output_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_file = tmp_path / "github_output"
        output_file.write_text("")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_github_outputs({"tier": "high", "blocked": "false"})

        contents = output_file.read_text()
        assert "tier=high\n" in contents
        assert "blocked=false\n" in contents

    def test_appends_to_existing_github_output_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_file = tmp_path / "github_output"
        output_file.write_text("existing=value\n")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_github_outputs({"tier": "low"})

        contents = output_file.read_text()
        assert contents.startswith("existing=value\n")
        assert "tier=low\n" in contents

    def test_multiline_value_uses_heredoc_syntax(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_file = tmp_path / "github_output"
        output_file.write_text("")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_github_outputs({"summary": "line1\nline2"})

        contents = output_file.read_text()
        assert "summary<<EOF\n" in contents
        assert "line1\nline2\nEOF\n" in contents

    def test_without_github_output_env_var_prints_to_stdout(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("GITHUB_OUTPUT", raising=False)

        write_github_outputs({"tier": "medium", "blocked": "true"})

        captured = capsys.readouterr()
        assert "::set-output name=tier::medium" in captured.out
        assert "::set-output name=blocked::true" in captured.out

    def test_empty_outputs_dict_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        output_file = tmp_path / "github_output"
        output_file.write_text("")
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        write_github_outputs({})

        assert output_file.read_text() == ""


# ─── print_summary ───────────────────────────────────────────────────────────


class TestPrintSummary:
    """Smoke tests: print_summary should not crash for various inputs."""

    def test_high_tier_with_violations_does_not_crash(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        violations = [
            {"file": "prod.env", "pattern": "*.env", "reason": "Env blocked"}
        ]
        print_summary(
            tier="high",
            changed_files=["prod.env", "apps/main.py"],
            required_checks=["tests", "claude-review"],
            blocked=True,
            violations=violations,
            tier_rules={"high": ["apps/**"], "low": ["*.md"]},
        )
        captured = capsys.readouterr()
        assert "HIGH" in captured.out
        assert "YES" in captured.out

    def test_low_tier_no_violations_does_not_crash(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        print_summary(
            tier="low",
            changed_files=["README.md"],
            required_checks=["risk-policy-gate"],
            blocked=False,
            violations=[],
            tier_rules={"low": ["*.md"]},
        )
        captured = capsys.readouterr()
        assert "LOW" in captured.out
        assert "NO" in captured.out

    def test_empty_changed_files_does_not_crash(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        print_summary(
            tier="low",
            changed_files=[],
            required_checks=["risk-policy-gate"],
            blocked=False,
            violations=[],
            tier_rules={},
        )
        captured = capsys.readouterr()
        assert "0 changed" in captured.out

    def test_many_files_truncates_display(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        files = [f"file_{i}.py" for i in range(30)]
        print_summary(
            tier="medium",
            changed_files=files,
            required_checks=["tests"],
            blocked=False,
            violations=[],
            tier_rules={"medium": ["*.py"]},
        )
        captured = capsys.readouterr()
        assert "and 10 more files" in captured.out

    def test_medium_tier_does_not_crash(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        print_summary(
            tier="medium",
            changed_files=["apps/orchestrator/models.py"],
            required_checks=["tests", "claude-review"],
            blocked=False,
            violations=[],
            tier_rules={"medium": ["apps/orchestrator/models.py"]},
        )
        captured = capsys.readouterr()
        assert "MEDIUM" in captured.out

    def test_unknown_tier_does_not_crash(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        print_summary(
            tier="unknown",
            changed_files=["file.py"],
            required_checks=[],
            blocked=False,
            violations=[],
            tier_rules={},
        )
        captured = capsys.readouterr()
        assert "UNKNOWN" in captured.out

    def test_multiple_violations_printed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        violations = [
            {"file": "a.env", "pattern": "*.env", "reason": "Blocked env"},
            {"file": "b.secret", "pattern": "*.secret", "reason": "Blocked secret"},
        ]
        print_summary(
            tier="high",
            changed_files=["a.env", "b.secret"],
            required_checks=["tests"],
            blocked=True,
            violations=violations,
            tier_rules={},
        )
        captured = capsys.readouterr()
        assert "2" in captured.out  # violation count
        assert "Blocked env" in captured.out
        assert "Blocked secret" in captured.out
