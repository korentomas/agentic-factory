"""Tests for apps.runner.workspace — git workspace management."""

from pathlib import Path
from unittest.mock import patch

import pytest

from apps.runner.workspace import (
    cleanup_workspace,
    commit_changes,
    create_workspace,
    get_workspace_root,
    list_changed_files,
    push_changes,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _git_ok(stdout: str = "") -> tuple[int, str, str]:
    """Simulate a successful git command."""
    return (0, stdout, "")


def _git_fail(stderr: str = "error") -> tuple[int, str, str]:
    """Simulate a failed git command."""
    return (1, "", stderr)


# ── get_workspace_root ───────────────────────────────────────────────────────


class TestGetWorkspaceRoot:
    """Tests for workspace root resolution."""

    def test_default_root(self, monkeypatch):
        monkeypatch.delenv("LAILATOV_WORKSPACE_ROOT", raising=False)
        root = get_workspace_root()
        assert root == Path("/tmp/lailatov-workspaces")

    def test_custom_root(self, monkeypatch):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", "/custom/path")
        root = get_workspace_root()
        assert root == Path("/custom/path")


# ── create_workspace ─────────────────────────────────────────────────────────


class TestCreateWorkspace:
    """Tests for workspace creation (clone + branch)."""

    @pytest.mark.asyncio
    async def test_create_success(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", str(tmp_path))

        call_log = []

        async def mock_run_git(args, cwd, env=None, timeout=300):
            call_log.append(args)
            if args[0] == "clone":
                # Simulate clone by creating repo dir
                repo_dir = cwd / "repo"
                repo_dir.mkdir(parents=True, exist_ok=True)
                return _git_ok()
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            path = await create_workspace(
                task_id="t1",
                repo_url="https://github.com/org/repo",
                branch="agent/t1",
                base_branch="main",
            )

        assert path == tmp_path / "t1" / "repo"
        assert (tmp_path / "t1" / "output").is_dir()
        assert (tmp_path / "t1" / "logs").is_dir()

        # Verify git commands: clone, checkout -b, config user.name, config user.email
        assert call_log[0][0] == "clone"
        assert call_log[1] == ["checkout", "-b", "agent/t1"]
        assert call_log[2] == ["config", "user.name", "LailaTov Agent"]
        assert call_log[3] == ["config", "user.email", "agent@lailatov.dev"]

    @pytest.mark.asyncio
    async def test_create_with_token(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", str(tmp_path))

        captured_url = []

        async def mock_run_git(args, cwd, env=None, timeout=300):
            if args[0] == "clone":
                captured_url.append(args[5])  # clone URL: clone --depth 1 --branch X <URL> repo
                (cwd / "repo").mkdir(parents=True, exist_ok=True)
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            await create_workspace(
                task_id="t2",
                repo_url="https://github.com/org/repo",
                branch="agent/t2",
                github_token="ghp_test123",
            )

        assert "x-access-token:ghp_test123@" in captured_url[0]

    @pytest.mark.asyncio
    async def test_create_clone_failure(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", str(tmp_path))

        async def mock_run_git(args, cwd, env=None, timeout=300):
            if args[0] == "clone":
                return _git_fail("fatal: repository not found")
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            with pytest.raises(RuntimeError, match="git clone failed"):
                await create_workspace(
                    task_id="t3",
                    repo_url="https://github.com/org/missing",
                    branch="agent/t3",
                )

    @pytest.mark.asyncio
    async def test_create_branch_failure(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", str(tmp_path))

        async def mock_run_git(args, cwd, env=None, timeout=300):
            if args[0] == "clone":
                (cwd / "repo").mkdir(parents=True, exist_ok=True)
                return _git_ok()
            if args[0] == "checkout":
                return _git_fail("branch already exists")
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            with pytest.raises(RuntimeError, match="checkout -b"):
                await create_workspace(
                    task_id="t4",
                    repo_url="https://github.com/org/repo",
                    branch="agent/t4",
                )

    @pytest.mark.asyncio
    async def test_create_cleans_stale_workspace(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", str(tmp_path))

        # Create a stale workspace
        stale = tmp_path / "t5"
        stale.mkdir()
        (stale / "old-file.txt").write_text("stale data")

        async def mock_run_git(args, cwd, env=None, timeout=300):
            if args[0] == "clone":
                (cwd / "repo").mkdir(parents=True, exist_ok=True)
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            await create_workspace(
                task_id="t5",
                repo_url="https://github.com/org/repo",
                branch="agent/t5",
            )

        # Stale file should be gone, fresh workspace should exist
        assert not (tmp_path / "t5" / "old-file.txt").exists()
        assert (tmp_path / "t5" / "repo").exists()


# ── commit_changes ───────────────────────────────────────────────────────────


class TestCommitChanges:
    """Tests for staging and committing."""

    @pytest.mark.asyncio
    async def test_commit_with_changes(self, tmp_path):
        call_log = []

        async def mock_run_git(args, cwd, env=None, timeout=300):
            call_log.append(args)
            if args[:2] == ["diff", "--cached"]:
                return (1, "", "")  # non-zero = there are changes
            if args[0] == "commit":
                return _git_ok()
            if args[:2] == ["rev-parse", "HEAD"]:
                return _git_ok("abc123def456")
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            sha = await commit_changes(tmp_path, "test commit")

        assert sha == "abc123def456"
        assert ["add", "-A"] in call_log
        assert ["commit", "-m", "test commit"] in call_log

    @pytest.mark.asyncio
    async def test_commit_nothing_to_commit(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            if args[:2] == ["diff", "--cached"]:
                return _git_ok()  # code 0 = no changes
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            sha = await commit_changes(tmp_path, "no changes")

        assert sha is None

    @pytest.mark.asyncio
    async def test_commit_failure(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            if args[:2] == ["diff", "--cached"]:
                return (1, "", "")  # there are changes
            if args[0] == "commit":
                return _git_fail("commit error")
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            sha = await commit_changes(tmp_path, "will fail")

        assert sha is None


# ── push_changes ─────────────────────────────────────────────────────────────


class TestPushChanges:
    """Tests for pushing to remote."""

    @pytest.mark.asyncio
    async def test_push_success(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            ok = await push_changes(tmp_path, "agent/t1")

        assert ok is True

    @pytest.mark.asyncio
    async def test_push_failure(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            return _git_fail("permission denied")

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            ok = await push_changes(tmp_path, "agent/t1")

        assert ok is False


# ── cleanup_workspace ────────────────────────────────────────────────────────


class TestCleanupWorkspace:
    """Tests for workspace cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_existing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", str(tmp_path))

        ws = tmp_path / "t1"
        ws.mkdir()
        (ws / "some-file").write_text("data")

        await cleanup_workspace("t1")
        assert not ws.exists()

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent(self, monkeypatch, tmp_path):
        monkeypatch.setenv("LAILATOV_WORKSPACE_ROOT", str(tmp_path))
        # Should not raise even if workspace doesn't exist
        await cleanup_workspace("nonexistent")


# ── list_changed_files ───────────────────────────────────────────────────────


class TestListChangedFiles:
    """Tests for listing changed files."""

    @pytest.mark.asyncio
    async def test_diff_from_base(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            if "origin/main...HEAD" in args:
                return _git_ok("src/foo.py\nsrc/bar.py")
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            files = await list_changed_files(tmp_path, "main")

        assert files == ["src/foo.py", "src/bar.py"]

    @pytest.mark.asyncio
    async def test_fallback_to_head(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            if "origin/main...HEAD" in args:
                return _git_fail("bad revision")
            if "HEAD~1" in args:
                return _git_ok("fallback.py")
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            files = await list_changed_files(tmp_path, "main")

        assert files == ["fallback.py"]

    @pytest.mark.asyncio
    async def test_no_changes(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            return _git_ok("")  # empty stdout

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            files = await list_changed_files(tmp_path, "main")

        assert files == []

    @pytest.mark.asyncio
    async def test_filters_blank_lines(self, tmp_path):
        async def mock_run_git(args, cwd, env=None, timeout=300):
            if "origin/main...HEAD" in args:
                return _git_ok("a.py\n\nb.py\n  \nc.py")
            return _git_ok()

        with patch("apps.runner.workspace._run_git", side_effect=mock_run_git):
            files = await list_changed_files(tmp_path, "main")

        assert files == ["a.py", "b.py", "c.py"]
