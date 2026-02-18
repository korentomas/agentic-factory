"""
Tests for apps.orchestrator.jobs.weekly_summary — weekly engineering digest.

Covers:
- WeeklyStats dataclass construction and serialization
- _run_git() subprocess execution and error handling
- _count_tests() pytest collection parsing
- _find_large_files() bash subprocess and output parsing
- _fetch_clickup_completed() async HTTP with ClickUp API
- gather_stats() orchestration of all data collection
- _build_summary_prompt() prompt generation from stats
- _call_agent() Claude agent invocation and error handling
- _post_to_slack() Slack webhook posting
- run_summary() end-to-end orchestration with fallback behavior
"""

from __future__ import annotations

import subprocess
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from apps.orchestrator.jobs.weekly_summary import (
    WeeklyStats,
    _build_summary_prompt,
    _call_agent,
    _count_tests,
    _fetch_clickup_completed,
    _find_large_files,
    _post_to_slack,
    _run_git,
    gather_stats,
    run_summary,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


_SENTINEL: object = object()


def _make_stats(
    week_ending: str = "2026-02-16",
    total_merges: int = 5,
    agent_merges: int = 3,
    manual_merges: int = 2,
    recent_merge_subjects: list[str] | object = _SENTINEL,
    total_test_count: int = 42,
    large_files: list[str] | object = _SENTINEL,
    clickup_completed_count: int = 7,
    clickup_completed_titles: list[str] | object = _SENTINEL,
) -> WeeklyStats:
    """Convenience builder: create a WeeklyStats with sensible defaults."""
    if recent_merge_subjects is _SENTINEL:
        recent_merge_subjects = ["Merge PR #1", "Merge PR #2"]
    if large_files is _SENTINEL:
        large_files = []
    if clickup_completed_titles is _SENTINEL:
        clickup_completed_titles = ["Task A", "Task B"]
    return WeeklyStats(
        week_ending=week_ending,
        total_merges=total_merges,
        agent_merges=agent_merges,
        manual_merges=manual_merges,
        recent_merge_subjects=recent_merge_subjects,  # type: ignore[arg-type]
        total_test_count=total_test_count,
        large_files=large_files,  # type: ignore[arg-type]
        clickup_completed_count=clickup_completed_count,
        clickup_completed_titles=clickup_completed_titles,  # type: ignore[arg-type]
    )


def _mock_subprocess_result(
    stdout: str = "",
    stderr: str = "",
    returncode: int = 0,
) -> subprocess.CompletedProcess[str]:
    """Create a mock subprocess.CompletedProcess."""
    return subprocess.CompletedProcess(
        args=["mock"],
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
    )


# ── 1. WeeklyStats dataclass ────────────────────────────────────────────────


class TestWeeklyStats:
    """WeeklyStats dataclass construction and serialization."""

    def test_construction_with_all_fields(self) -> None:
        stats = _make_stats()
        assert stats.week_ending == "2026-02-16"
        assert stats.total_merges == 5
        assert stats.agent_merges == 3
        assert stats.manual_merges == 2
        assert stats.total_test_count == 42
        assert stats.clickup_completed_count == 7

    def test_asdict_contains_all_keys(self) -> None:
        stats = _make_stats()
        d = asdict(stats)
        expected_keys = {
            "week_ending",
            "total_merges",
            "agent_merges",
            "manual_merges",
            "recent_merge_subjects",
            "total_test_count",
            "large_files",
            "clickup_completed_count",
            "clickup_completed_titles",
        }
        assert set(d.keys()) == expected_keys

    def test_empty_lists_allowed(self) -> None:
        stats = _make_stats(
            recent_merge_subjects=[],
            large_files=[],
            clickup_completed_titles=[],
        )
        assert stats.recent_merge_subjects == []
        assert stats.large_files == []
        assert stats.clickup_completed_titles == []

    def test_zero_counts_allowed(self) -> None:
        stats = _make_stats(
            total_merges=0,
            agent_merges=0,
            manual_merges=0,
            total_test_count=0,
            clickup_completed_count=0,
        )
        assert stats.total_merges == 0
        assert stats.total_test_count == 0


# ── 2. _run_git() ───────────────────────────────────────────────────────────


class TestRunGit:
    """_run_git() subprocess execution and error handling."""

    def test_successful_git_command_returns_stdout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="  commit subject line  \n")
        with patch("subprocess.run", return_value=result) as mock_run:
            output = _run_git(["log", "--oneline"])
            mock_run.assert_called_once_with(
                ["git", "log", "--oneline"],
                cwd="/tmp/repo",
                capture_output=True,
                text=True,
                timeout=30,
            )
        assert output == "commit subject line"

    def test_uses_dot_when_repo_path_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("REPO_PATH", raising=False)
        result = _mock_subprocess_result(stdout="ok")
        with patch("subprocess.run", return_value=result) as mock_run:
            _run_git(["status"])
            assert mock_run.call_args[1]["cwd"] == "."

    def test_explicit_cwd_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/env/path")
        result = _mock_subprocess_result(stdout="ok")
        with patch("subprocess.run", return_value=result) as mock_run:
            _run_git(["status"], cwd="/explicit/path")
            assert mock_run.call_args[1]["cwd"] == "/explicit/path"

    def test_nonzero_returncode_returns_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(returncode=128, stderr="fatal: not a git repo")
        with patch("subprocess.run", return_value=result):
            assert _run_git(["log"]) == ""

    def test_timeout_returns_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30)):
            assert _run_git(["log"]) == ""

    def test_file_not_found_returns_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=FileNotFoundError("git not found")):
            assert _run_git(["status"]) == ""

    def test_oserror_returns_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=OSError("OS failure")):
            assert _run_git(["status"]) == ""

    def test_stdout_is_stripped(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="\n  output with whitespace \n\n")
        with patch("subprocess.run", return_value=result):
            assert _run_git(["log"]) == "output with whitespace"

    def test_empty_stdout_returns_empty_string(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="")
        with patch("subprocess.run", return_value=result):
            assert _run_git(["log"]) == ""


# ── 3. _count_tests() ───────────────────────────────────────────────────────


class TestCountTests:
    """_count_tests() pytest collection parsing."""

    def test_parses_collected_count_from_stdout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="42 tests collected\n")
        with patch("subprocess.run", return_value=result):
            assert _count_tests() == 42

    def test_parses_selected_count_from_stdout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="15 selected\n")
        with patch("subprocess.run", return_value=result):
            assert _count_tests() == 15

    def test_parses_count_from_stderr_when_not_in_stdout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="", stderr="8 tests collected\n")
        with patch("subprocess.run", return_value=result):
            assert _count_tests() == 8

    def test_returns_zero_when_no_match_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="no tests ran\n")
        with patch("subprocess.run", return_value=result):
            assert _count_tests() == 0

    def test_returns_zero_on_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        err = subprocess.TimeoutExpired(cmd="pytest", timeout=60)
        with patch("subprocess.run", side_effect=err):
            assert _count_tests() == 0

    def test_returns_zero_on_file_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=FileNotFoundError("python not found")):
            assert _count_tests() == 0

    def test_returns_zero_on_os_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=OSError("OS failure")):
            assert _count_tests() == 0

    def test_uses_dot_when_repo_path_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("REPO_PATH", raising=False)
        result = _mock_subprocess_result(stdout="0 tests collected\n")
        with patch("subprocess.run", return_value=result) as mock_run:
            _count_tests()
            assert mock_run.call_args[1]["cwd"] == "."

    def test_explicit_cwd_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/env/path")
        result = _mock_subprocess_result(stdout="5 tests collected\n")
        with patch("subprocess.run", return_value=result) as mock_run:
            _count_tests(cwd="/explicit/path")
            assert mock_run.call_args[1]["cwd"] == "/explicit/path"

    def test_multiline_output_picks_first_match(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        stdout = "test_one.py::test_a\ntest_two.py::test_b\n10 tests collected\n"
        result = _mock_subprocess_result(stdout=stdout)
        with patch("subprocess.run", return_value=result):
            assert _count_tests() == 10

    def test_non_digit_first_word_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="no tests collected\n")
        with patch("subprocess.run", return_value=result):
            assert _count_tests() == 0


# ── 4. _find_large_files() ──────────────────────────────────────────────────


class TestFindLargeFiles:
    """_find_large_files() bash subprocess and output parsing."""

    def test_returns_list_of_large_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        stdout = "./apps/main.py (450 lines)\n./apps/models.py (320 lines)\n"
        result = _mock_subprocess_result(stdout=stdout)
        with patch("subprocess.run", return_value=result):
            files = _find_large_files()
        assert files == ["./apps/main.py (450 lines)", "./apps/models.py (320 lines)"]

    def test_returns_empty_list_when_no_large_files(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(stdout="")
        with patch("subprocess.run", return_value=result):
            assert _find_large_files() == []

    def test_returns_empty_list_on_nonzero_returncode(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        result = _mock_subprocess_result(returncode=1, stdout="some output")
        with patch("subprocess.run", return_value=result):
            assert _find_large_files() == []

    def test_returns_empty_list_on_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="bash", timeout=30)):
            assert _find_large_files() == []

    def test_returns_empty_list_on_file_not_found(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=FileNotFoundError("bash not found")):
            assert _find_large_files() == []

    def test_returns_empty_list_on_os_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        with patch("subprocess.run", side_effect=OSError("OS failure")):
            assert _find_large_files() == []

    def test_strips_whitespace_from_lines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        stdout = "  ./file.py (500 lines)  \n  ./other.py (400 lines)  \n"
        result = _mock_subprocess_result(stdout=stdout)
        with patch("subprocess.run", return_value=result):
            files = _find_large_files()
        assert files == ["./file.py (500 lines)", "./other.py (400 lines)"]

    def test_skips_empty_lines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/tmp/repo")
        stdout = "./file.py (500 lines)\n\n\n./other.py (400 lines)\n\n"
        result = _mock_subprocess_result(stdout=stdout)
        with patch("subprocess.run", return_value=result):
            files = _find_large_files()
        assert len(files) == 2

    def test_uses_dot_when_repo_path_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("REPO_PATH", raising=False)
        result = _mock_subprocess_result(stdout="")
        with patch("subprocess.run", return_value=result) as mock_run:
            _find_large_files()
            assert mock_run.call_args[1]["cwd"] == "."

    def test_explicit_cwd_overrides_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REPO_PATH", "/env/path")
        result = _mock_subprocess_result(stdout="")
        with patch("subprocess.run", return_value=result) as mock_run:
            _find_large_files(cwd="/explicit/path")
            assert mock_run.call_args[1]["cwd"] == "/explicit/path"


# ── 5. _fetch_clickup_completed() ───────────────────────────────────────────


class TestFetchClickupCompleted:
    """_fetch_clickup_completed() async HTTP with ClickUp API."""

    async def test_returns_count_and_titles_on_success(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tasks": [
                {"name": "Task Alpha"},
                {"name": "Task Beta"},
                {"name": "Task Gamma"},
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 3
        assert titles == ["Task Alpha", "Task Beta", "Task Gamma"]

    async def test_returns_zeros_when_token_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 0
        assert titles == []
        mock_client.get.assert_not_called()

    async def test_returns_zeros_when_team_id_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.delenv("CLICKUP_TEAM_ID", raising=False)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 0
        assert titles == []
        mock_client.get.assert_not_called()

    async def test_returns_zeros_when_both_vars_missing(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
        monkeypatch.delenv("CLICKUP_TEAM_ID", raising=False)

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 0
        assert titles == []

    async def test_caps_titles_at_ten(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        tasks = [{"name": f"Task {i}"} for i in range(15)]
        mock_response = MagicMock()
        mock_response.json.return_value = {"tasks": tasks}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 15
        assert len(titles) == 10

    async def test_returns_zeros_on_http_status_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Unauthorized",
                request=httpx.Request("GET", "https://api.clickup.com/api/v2/team/t/task"),
                response=httpx.Response(401, text="Unauthorized"),
            )
        )

        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 0
        assert titles == []

    async def test_returns_zeros_on_request_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(
            side_effect=httpx.RequestError(
                "Connection refused",
                request=httpx.Request("GET", "https://api.clickup.com/api/v2/team/t/task"),
            )
        )

        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 0
        assert titles == []

    async def test_uses_correct_url_with_team_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "my-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "99887766")

        mock_response = MagicMock()
        mock_response.json.return_value = {"tasks": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        await _fetch_clickup_completed(mock_client)

        call_args = mock_client.get.call_args
        assert "99887766" in call_args[0][0]
        assert call_args[1]["headers"]["Authorization"] == "my-token"

    async def test_handles_empty_tasks_list(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        mock_response = MagicMock()
        mock_response.json.return_value = {"tasks": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 0
        assert titles == []

    async def test_handles_missing_tasks_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 0
        assert titles == []

    async def test_handles_task_with_missing_name(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        mock_response = MagicMock()
        mock_response.json.return_value = {
            "tasks": [{"id": "1"}, {"name": "Has Name"}]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock(spec=httpx.AsyncClient)
        mock_client.get = AsyncMock(return_value=mock_response)

        count, titles = await _fetch_clickup_completed(mock_client)
        assert count == 2
        assert titles == ["", "Has Name"]


# ── 6. gather_stats() ───────────────────────────────────────────────────────


class TestGatherStats:
    """gather_stats() orchestration of all data collection."""

    async def test_returns_weekly_stats_with_all_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("CLICKUP_API_TOKEN", "test-token")
        monkeypatch.setenv("CLICKUP_TEAM_ID", "team-123")

        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary._run_git",
                side_effect=[
                    # all_merges_raw: 3 merge subjects
                    "Merge PR #1\nMerge PR #2\nMerge agent/cu-3",
                    # agent_merges_raw: 1 agent merge
                    "Merge agent/cu-3",
                ],
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._count_tests",
                return_value=50,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._find_large_files",
                return_value=["./big.py (400 lines)"],
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._fetch_clickup_completed",
                return_value=(5, ["Done task 1", "Done task 2"]),
            ),
        ):
            stats = await gather_stats()

        assert isinstance(stats, WeeklyStats)
        assert stats.total_merges == 3
        assert stats.agent_merges == 1
        assert stats.manual_merges == 2
        assert stats.recent_merge_subjects == ["Merge PR #1", "Merge PR #2", "Merge agent/cu-3"]
        assert stats.total_test_count == 50
        assert stats.large_files == ["./big.py (400 lines)"]
        assert stats.clickup_completed_count == 5
        assert stats.clickup_completed_titles == ["Done task 1", "Done task 2"]

    async def test_handles_empty_git_output(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
        monkeypatch.delenv("CLICKUP_TEAM_ID", raising=False)

        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary._run_git",
                return_value="",
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._count_tests",
                return_value=0,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._find_large_files",
                return_value=[],
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._fetch_clickup_completed",
                return_value=(0, []),
            ),
        ):
            stats = await gather_stats()

        assert stats.total_merges == 0
        assert stats.agent_merges == 0
        assert stats.manual_merges == 0
        assert stats.recent_merge_subjects == []
        assert stats.clickup_completed_count == 0

    async def test_recent_merge_subjects_capped_at_ten(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
        monkeypatch.delenv("CLICKUP_TEAM_ID", raising=False)

        merge_lines = "\n".join([f"Merge PR #{i}" for i in range(15)])
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary._run_git",
                side_effect=[merge_lines, ""],
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._count_tests",
                return_value=0,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._find_large_files",
                return_value=[],
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._fetch_clickup_completed",
                return_value=(0, []),
            ),
        ):
            stats = await gather_stats()

        assert len(stats.recent_merge_subjects) == 10

    async def test_week_ending_is_iso_date(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("CLICKUP_API_TOKEN", raising=False)
        monkeypatch.delenv("CLICKUP_TEAM_ID", raising=False)

        with (
            patch("apps.orchestrator.jobs.weekly_summary._run_git", return_value=""),
            patch("apps.orchestrator.jobs.weekly_summary._count_tests", return_value=0),
            patch("apps.orchestrator.jobs.weekly_summary._find_large_files", return_value=[]),
            patch(
                "apps.orchestrator.jobs.weekly_summary._fetch_clickup_completed",
                return_value=(0, []),
            ),
        ):
            stats = await gather_stats()

        # Should be YYYY-MM-DD format
        parts = stats.week_ending.split("-")
        assert len(parts) == 3
        assert len(parts[0]) == 4
        assert len(parts[1]) == 2
        assert len(parts[2]) == 2


# ── 7. _build_summary_prompt() ──────────────────────────────────────────────


class TestBuildSummaryPrompt:
    """_build_summary_prompt() prompt generation from stats."""

    def test_prompt_contains_week_ending(self) -> None:
        stats = _make_stats(week_ending="2026-02-16")
        prompt = _build_summary_prompt(stats)
        assert "2026-02-16" in prompt

    def test_prompt_contains_stats_json(self) -> None:
        stats = _make_stats(total_merges=12, agent_merges=8)
        prompt = _build_summary_prompt(stats)
        assert '"total_merges": 12' in prompt
        assert '"agent_merges": 8' in prompt

    def test_prompt_contains_merge_subjects(self) -> None:
        stats = _make_stats(recent_merge_subjects=["Fix login bug", "Add API endpoint"])
        prompt = _build_summary_prompt(stats)
        assert "Fix login bug" in prompt
        assert "Add API endpoint" in prompt

    def test_prompt_contains_large_files(self) -> None:
        stats = _make_stats(large_files=["./apps/big.py (500 lines)"])
        prompt = _build_summary_prompt(stats)
        assert "./apps/big.py (500 lines)" in prompt

    def test_prompt_contains_clickup_titles(self) -> None:
        stats = _make_stats(clickup_completed_titles=["Deploy v2", "Fix bug #42"])
        prompt = _build_summary_prompt(stats)
        assert "Deploy v2" in prompt
        assert "Fix bug #42" in prompt

    def test_prompt_contains_formatting_instructions(self) -> None:
        stats = _make_stats()
        prompt = _build_summary_prompt(stats)
        assert "Slack" in prompt
        assert "Max 25 lines" in prompt
        assert "Do not invent numbers" in prompt

    def test_prompt_with_empty_stats(self) -> None:
        stats = _make_stats(
            total_merges=0,
            agent_merges=0,
            manual_merges=0,
            recent_merge_subjects=[],
            total_test_count=0,
            large_files=[],
            clickup_completed_count=0,
            clickup_completed_titles=[],
        )
        prompt = _build_summary_prompt(stats)
        assert '"total_merges": 0' in prompt
        assert '"total_test_count": 0' in prompt

    def test_prompt_is_non_empty_string(self) -> None:
        stats = _make_stats()
        prompt = _build_summary_prompt(stats)
        assert isinstance(prompt, str)
        assert len(prompt) > 100  # Reasonable minimum for a prompt


# ── 8. _call_agent() ────────────────────────────────────────────────────────


class TestCallAgent:
    """_call_agent() Claude agent invocation and error handling."""

    async def test_raises_runtime_error_when_sdk_not_installed(self) -> None:
        with patch.dict("sys.modules", {"claude_agent_sdk": None}):
            with pytest.raises(RuntimeError, match="claude-agent-sdk not installed"):
                await _call_agent("test prompt")

    async def test_returns_collected_text(self) -> None:
        mock_message_text = MagicMock()
        mock_message_text.text = "Weekly summary content"
        mock_message_text.result = None

        mock_message_result = MagicMock()
        mock_message_result.text = None
        mock_message_result.result = "Final result text"

        async def mock_query(prompt, options):
            yield mock_message_text
            yield mock_message_result

        mock_sdk = MagicMock()
        mock_sdk.query = mock_query
        mock_sdk.ClaudeAgentOptions = MagicMock()

        with patch.dict("sys.modules", {"claude_agent_sdk": mock_sdk}):
            result = await _call_agent("test prompt")

        assert "Weekly summary content" in result
        assert "Final result text" in result

    async def test_raises_runtime_error_on_empty_response(self) -> None:
        async def mock_query(prompt, options):
            mock_msg = MagicMock()
            mock_msg.text = None
            mock_msg.result = None
            yield mock_msg

        mock_sdk = MagicMock()
        mock_sdk.query = mock_query
        mock_sdk.ClaudeAgentOptions = MagicMock()

        with patch.dict("sys.modules", {"claude_agent_sdk": mock_sdk}):
            with pytest.raises(RuntimeError, match="Agent returned empty summary"):
                await _call_agent("test prompt")

    async def test_collects_only_text_messages(self) -> None:
        mock_msg1 = MagicMock()
        mock_msg1.text = "Part one."
        mock_msg1.result = None

        mock_msg2 = MagicMock()
        mock_msg2.text = "Part two."
        mock_msg2.result = None

        async def mock_query(prompt, options):
            yield mock_msg1
            yield mock_msg2

        mock_sdk = MagicMock()
        mock_sdk.query = mock_query
        mock_sdk.ClaudeAgentOptions = MagicMock()

        with patch.dict("sys.modules", {"claude_agent_sdk": mock_sdk}):
            result = await _call_agent("test prompt")

        assert "Part one." in result
        assert "Part two." in result

    async def test_strips_whitespace_from_result(self) -> None:
        mock_msg = MagicMock()
        mock_msg.text = "  content with spaces  "
        mock_msg.result = None

        async def mock_query(prompt, options):
            yield mock_msg

        mock_sdk = MagicMock()
        mock_sdk.query = mock_query
        mock_sdk.ClaudeAgentOptions = MagicMock()

        with patch.dict("sys.modules", {"claude_agent_sdk": mock_sdk}):
            result = await _call_agent("test prompt")

        assert result == "content with spaces"


# ── 9. _post_to_slack() ─────────────────────────────────────────────────────


class TestPostToSlack:
    """_post_to_slack() Slack webhook posting."""

    async def test_posts_text_to_slack_webhook(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        monkeypatch.setenv("SLACK_CHANNEL", "eng-updates")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await _post_to_slack("Hello Slack!")

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/test"
        payload = call_args[1]["json"]
        assert payload["text"] == "Hello Slack!"
        assert payload["channel"] == "eng-updates"

    async def test_uses_default_channel_when_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
        monkeypatch.delenv("SLACK_CHANNEL", raising=False)

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await _post_to_slack("Hello!")

        payload = mock_client.post.call_args[1]["json"]
        assert payload["channel"] == "dev-agents"

    async def test_skips_post_when_webhook_url_not_set(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)

        await _post_to_slack("This goes to stdout instead")

        captured = capsys.readouterr()
        assert "Slack not configured" in captured.out
        assert "This goes to stdout instead" in captured.out

    async def test_raises_on_http_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Request",
                request=httpx.Request("POST", "https://hooks.slack.com/test"),
                response=httpx.Response(400, text="invalid_payload"),
            )
        )

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(httpx.HTTPStatusError):
                await _post_to_slack("This will fail")


# ── 10. run_summary() ───────────────────────────────────────────────────────


class TestRunSummary:
    """run_summary() end-to-end orchestration with fallback behavior."""

    async def test_returns_1_when_anthropic_api_key_not_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = await run_summary()
        assert result == 1

    async def test_successful_end_to_end_returns_0(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats()
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                return_value="Generated summary text",
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
            ) as mock_slack,
        ):
            result = await run_summary()

        assert result == 0
        mock_slack.assert_called_once_with("Generated summary text")

    async def test_returns_1_when_gather_stats_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        with patch(
            "apps.orchestrator.jobs.weekly_summary.gather_stats",
            side_effect=RuntimeError("git explosion"),
        ):
            result = await run_summary()

        assert result == 1

    async def test_falls_back_to_minimal_summary_when_agent_raises_runtime_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats(total_merges=5, agent_merges=3, manual_merges=2)
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                side_effect=RuntimeError("Agent returned empty summary"),
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
            ) as mock_slack,
        ):
            result = await run_summary()

        assert result == 0
        # The fallback summary should have been posted
        posted_text = mock_slack.call_args[0][0]
        assert "Weekly Engineering Digest" in posted_text
        assert "5" in posted_text
        assert "3 agent-written" in posted_text
        assert "2 manual" in posted_text
        assert "Agent narrative unavailable" in posted_text

    async def test_returns_1_when_agent_raises_unexpected_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats()
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                side_effect=ValueError("Unexpected SDK error"),
            ),
        ):
            result = await run_summary()

        assert result == 1

    async def test_returns_1_when_slack_raises_http_error(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats()
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                return_value="Good summary text",
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
                side_effect=httpx.HTTPStatusError(
                    "Slack error",
                    request=httpx.Request("POST", "https://hooks.slack.com/test"),
                    response=httpx.Response(500, text="server error"),
                ),
            ),
        ):
            result = await run_summary()

        assert result == 1

    async def test_returns_1_when_slack_raises_unexpected_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats()
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                return_value="Good summary text",
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
                side_effect=ConnectionError("Network down"),
            ),
        ):
            result = await run_summary()

        assert result == 1

    async def test_fallback_summary_includes_test_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats(total_test_count=99)
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                side_effect=RuntimeError("Agent failed"),
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
            ) as mock_slack,
        ):
            result = await run_summary()

        assert result == 0
        posted_text = mock_slack.call_args[0][0]
        assert "99" in posted_text

    async def test_fallback_summary_includes_clickup_count(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats(clickup_completed_count=12)
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                side_effect=RuntimeError("Agent failed"),
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
            ) as mock_slack,
        ):
            result = await run_summary()

        assert result == 0
        posted_text = mock_slack.call_args[0][0]
        assert "12" in posted_text

    async def test_calls_build_summary_prompt_with_stats(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats()
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._build_summary_prompt",
                return_value="mocked prompt",
            ) as mock_prompt,
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                return_value="Summary text",
            ) as mock_agent,
            patch("apps.orchestrator.jobs.weekly_summary._post_to_slack"),
        ):
            result = await run_summary()

        assert result == 0
        mock_prompt.assert_called_once_with(stats)
        mock_agent.assert_called_once_with("mocked prompt")

    async def test_summary_text_passed_to_slack(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats()
        expected_text = "The weekly digest is here!"
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                return_value=expected_text,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
            ) as mock_slack,
        ):
            await run_summary()

        mock_slack.assert_called_once_with(expected_text)

    async def test_fallback_summary_includes_week_ending(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        stats = _make_stats(week_ending="2026-02-16")
        with (
            patch(
                "apps.orchestrator.jobs.weekly_summary.gather_stats",
                return_value=stats,
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._call_agent",
                side_effect=RuntimeError("Agent failed"),
            ),
            patch(
                "apps.orchestrator.jobs.weekly_summary._post_to_slack",
            ) as mock_slack,
        ):
            await run_summary()

        posted_text = mock_slack.call_args[0][0]
        assert "2026-02-16" in posted_text
