"""Tests for apps.runner.models — domain types for the Agent Runner."""

import pytest

from apps.runner.models import (
    RunnerResult,
    RunnerTask,
    TaskState,
    TaskStatus,
    generate_task_id,
)


class TestRunnerTask:
    """Tests for RunnerTask dataclass."""

    def test_create_minimal(self):
        task = RunnerTask(
            task_id="gh-42",
            repo_url="https://github.com/org/repo",
            branch="agent/gh-42",
            base_branch="main",
            description="Fix the login bug",
        )
        assert task.task_id == "gh-42"
        assert task.repo_url == "https://github.com/org/repo"
        assert task.risk_tier == "medium"
        assert task.complexity == "standard"
        assert task.max_turns == 40
        assert task.timeout_seconds == 3600

    def test_create_with_all_fields(self):
        task = RunnerTask(
            task_id="cu-abc123",
            repo_url="https://github.com/org/repo",
            branch="agent/cu-abc123",
            base_branch="develop",
            title="Add auth endpoint",
            description="Create POST /auth/login",
            risk_tier="high",
            complexity="high",
            engine="claude-code",
            model="claude-opus-4-6",
            max_turns=20,
            timeout_seconds=7200,
            env_vars={"EXTRA": "val"},
            constitution="Be thorough.",
            callback_url="https://api.example.com/callback",
        )
        assert task.risk_tier == "high"
        assert task.engine == "claude-code"
        assert task.env_vars == {"EXTRA": "val"}

    def test_empty_task_id_raises(self):
        with pytest.raises(ValueError, match="task_id is required"):
            RunnerTask(
                task_id="",
                repo_url="https://github.com/org/repo",
                branch="b",
                base_branch="main",
                description="desc",
            )

    def test_empty_repo_url_raises(self):
        with pytest.raises(ValueError, match="repo_url is required"):
            RunnerTask(
                task_id="t1",
                repo_url="",
                branch="b",
                base_branch="main",
                description="desc",
            )

    def test_empty_description_raises(self):
        with pytest.raises(ValueError, match="description is required"):
            RunnerTask(
                task_id="t1",
                repo_url="https://github.com/org/repo",
                branch="b",
                base_branch="main",
                description="",
            )

    def test_frozen(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        with pytest.raises(AttributeError):
            task.task_id = "changed"


class TestRunnerResult:
    """Tests for RunnerResult dataclass."""

    def test_success_result(self):
        result = RunnerResult(
            task_id="gh-42",
            status="success",
            engine="claude-code",
            model="claude-sonnet-4-6",
            files_changed=["src/auth.py", "tests/test_auth.py"],
            cost_usd=0.15,
            num_turns=12,
            duration_ms=45000,
            commit_sha="abc123",
        )
        assert result.status == "success"
        assert len(result.files_changed) == 2
        assert result.error_message is None

    def test_failure_result(self):
        result = RunnerResult(
            task_id="gh-42",
            status="failure",
            engine="aider",
            model="deepseek-chat",
            error_message="Process exited with code 1",
        )
        assert result.status == "failure"
        assert result.error_message is not None
        assert result.cost_usd == 0.0

    def test_defaults(self):
        result = RunnerResult(
            task_id="t1",
            status="success",
            engine="aider",
            model="gpt-4.1",
        )
        assert result.files_changed == []
        assert result.cost_usd == 0.0
        assert result.num_turns == 0
        assert result.commit_sha is None


class TestTaskState:
    """Tests for TaskState mutable state tracker."""

    def test_initial_state(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        state = TaskState(task=task)
        assert state.status == TaskStatus.PENDING
        assert state.result is None
        assert state.workspace_path is None

    def test_mutable(self):
        task = RunnerTask(
            task_id="t1",
            repo_url="https://github.com/org/repo",
            branch="b",
            base_branch="main",
            description="desc",
        )
        state = TaskState(task=task)
        state.status = TaskStatus.RUNNING
        assert state.status == TaskStatus.RUNNING


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_all_statuses_exist(self):
        assert TaskStatus.PENDING == "pending"
        assert TaskStatus.RUNNING == "running"
        assert TaskStatus.COMMITTING == "committing"
        assert TaskStatus.COMPLETE == "complete"
        assert TaskStatus.FAILED == "failed"
        assert TaskStatus.CANCELLED == "cancelled"
        assert TaskStatus.TIMED_OUT == "timed_out"


class TestGenerateTaskId:
    """Tests for task ID generation."""

    def test_format(self):
        tid = generate_task_id()
        assert tid.startswith("run-")
        assert len(tid) == 16  # "run-" + 12 hex chars

    def test_unique(self):
        ids = {generate_task_id() for _ in range(100)}
        assert len(ids) == 100
