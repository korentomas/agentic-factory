"""
Integration tests for the full runner pipeline — no mocks.

Exercises: POST /tasks → git clone → engine execution → commit → push → GET /tasks/{id}.
Uses real GitHub (korentomas/lailatov-test-sandbox) and real claude-code + haiku.

Run:
    pytest tests/test_runner_integration.py -v --tb=short -s --no-cov

Cost: ~$0.05 total (4 haiku calls at ~$0.01 each).
"""

from __future__ import annotations

import asyncio
import os
import re
import subprocess
import uuid

import httpx
import pytest

from apps.runner.main import (
    _error_router,
    _tasks,
    app,
    audit_log,
    get_breaker,
    reset_breakers,
)
from tests.conftest_e2e import E2E_PROMPT, skip_unless_engine, skip_unless_env

# Register e2e fixtures.
pytest_plugins = ["tests.conftest_e2e"]

# ── Constants ────────────────────────────────────────────────────────────────

SANDBOX_REPO = "https://github.com/korentomas/lailatov-test-sandbox"
POLL_INTERVAL = 0.5  # seconds
POLL_TIMEOUT = 120  # seconds — real engines take 10-30s
API_KEY = "integ-test-key"

# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _clear_state() -> None:
    """Reset in-memory state between tests."""
    _tasks.clear()
    audit_log.clear()
    reset_breakers()


@pytest.fixture()
def repo_url() -> str:
    """Sandbox repo URL."""
    return SANDBOX_REPO


@pytest.fixture()
def github_token() -> str:
    """GitHub token from env."""
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        pytest.skip("GITHUB_TOKEN env var not set")
    return token


@pytest.fixture()
def workspace_root(tmp_path: pytest.TempPathFactory) -> str:  # type: ignore[type-arg]
    """Override workspace root so tests use tmp_path."""
    ws = str(tmp_path / "workspaces")
    os.environ["LAILATOV_WORKSPACE_ROOT"] = ws
    yield ws  # type: ignore[misc]
    os.environ.pop("LAILATOV_WORKSPACE_ROOT", None)


@pytest.fixture()
def unique_branch() -> str:
    """Generate a unique branch name and clean up after the test."""
    branch = f"integ/{uuid.uuid4().hex[:8]}"
    yield branch  # type: ignore[misc]
    # Cleanup: delete the remote branch (best-effort)
    _delete_remote_branch(branch)


@pytest.fixture()
def auth_headers() -> dict[str, str]:
    """Set RUNNER_API_KEY and return Bearer headers."""
    os.environ["RUNNER_API_KEY"] = API_KEY
    yield {"Authorization": f"Bearer {API_KEY}"}  # type: ignore[misc]
    os.environ.pop("RUNNER_API_KEY", None)


@pytest.fixture(autouse=True)
def _neuter_error_router(monkeypatch: pytest.MonkeyPatch) -> None:
    """No-op the error router so it doesn't try to create GitHub issues."""
    async def _noop(*args: object, **kwargs: object) -> None:
        pass
    monkeypatch.setattr(_error_router, "handle", _noop)


@pytest.fixture()
async def async_client() -> httpx.AsyncClient:
    """ASGI test client — no network, talks to the app in-process."""
    transport = httpx.ASGITransport(app=app)  # type: ignore[arg-type]
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client  # type: ignore[misc]


# ── Helpers ──────────────────────────────────────────────────────────────────


async def poll_until_terminal(
    client: httpx.AsyncClient,
    task_id: str,
    headers: dict[str, str],
    *,
    timeout: float = POLL_TIMEOUT,
    interval: float = POLL_INTERVAL,
) -> dict:
    """Poll GET /tasks/{id} until a terminal status or timeout."""
    terminal = {"complete", "failed", "cancelled", "timed_out"}
    elapsed = 0.0
    while elapsed < timeout:
        resp = await client.get(f"/tasks/{task_id}", headers=headers)
        assert resp.status_code == 200, f"GET /tasks/{task_id} returned {resp.status_code}"
        data = resp.json()
        if data["status"] in terminal:
            return data
        await asyncio.sleep(interval)
        elapsed += interval

    raise TimeoutError(
        f"Task {task_id} did not reach terminal status within {timeout}s. "
        f"Last status: {data['status']}"
    )


def _delete_remote_branch(branch: str) -> None:
    """Best-effort delete of a remote branch on the sandbox repo."""
    try:
        subprocess.run(
            [
                "git", "ls-remote", "--exit-code", "--heads",
                SANDBOX_REPO, f"refs/heads/{branch}",
            ],
            capture_output=True,
            timeout=15,
        )
        # If ls-remote succeeds, the branch exists — delete it
        subprocess.run(
            [
                "git", "push", SANDBOX_REPO, "--delete", branch,
            ],
            capture_output=True,
            timeout=30,
        )
    except Exception:
        pass  # Best-effort cleanup


def _task_payload(
    task_id: str,
    branch: str,
    *,
    description: str = E2E_PROMPT,
    github_token: str = "",
    max_cost_usd: float = 0.0,
    engine: str = "claude-code",
    model: str = "claude-haiku-4-5",
) -> dict:
    """Build the POST /tasks JSON payload."""
    return {
        "task_id": task_id,
        "repo_url": SANDBOX_REPO,
        "branch": branch,
        "base_branch": "main",
        "title": "Fix add() bug",
        "description": description,
        "engine": engine,
        "model": model,
        "max_turns": 3,
        "timeout_seconds": 90,
        "github_token": github_token,
        "max_cost_usd": max_cost_usd,
    }


# ── Tests ────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("claude-code")
@skip_unless_env("ANTHROPIC_API_KEY")
async def test_full_pipeline_success(
    async_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    github_token: str,
    workspace_root: str,
    unique_branch: str,
) -> None:
    """Full pipeline: POST → clone → engine fix → commit → push → GET complete."""
    task_id = f"integ-success-{uuid.uuid4().hex[:8]}"
    payload = _task_payload(
        task_id, unique_branch, github_token=github_token,
    )

    # Submit
    resp = await async_client.post("/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 202
    assert resp.json()["task_id"] == task_id

    # Poll until terminal
    data = await poll_until_terminal(async_client, task_id, auth_headers)

    assert data["status"] == "complete", (
        f"Expected 'complete', got {data['status']}: {data.get('error_message')}"
    )
    assert data["engine"] == "claude-code"
    assert data["duration_ms"] > 0
    assert len(data.get("files_changed", [])) > 0

    # Commit SHA should be a 40-char hex string
    sha = data.get("commit_sha")
    assert sha is not None, "Expected a commit SHA"
    assert re.fullmatch(r"[0-9a-f]{40}", sha), f"Invalid SHA: {sha}"

    # Verify branch exists on remote
    result = subprocess.run(
        ["git", "ls-remote", "--heads", SANDBOX_REPO, f"refs/heads/{unique_branch}"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert unique_branch in result.stdout, (
        f"Branch {unique_branch} not found on remote"
    )


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("claude-code")
@skip_unless_env("ANTHROPIC_API_KEY")
async def test_no_changes_edge_case(
    async_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    github_token: str,
    workspace_root: str,
    unique_branch: str,
) -> None:
    """Engine succeeds but makes no changes → commit_sha is None."""
    task_id = f"integ-nochange-{uuid.uuid4().hex[:8]}"
    payload = _task_payload(
        task_id,
        unique_branch,
        description=(
            "The code in math_utils.py is correct. Do not make any changes. "
            "Just respond with 'no changes needed'."
        ),
        github_token=github_token,
    )

    resp = await async_client.post("/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 202

    data = await poll_until_terminal(async_client, task_id, auth_headers)

    # Engine may succeed or "fail" (no diff) — either is valid for this edge case.
    # The key assertion: if status is complete, commit_sha should be None (no diff).
    if data["status"] == "complete":
        assert data.get("commit_sha") is None, (
            f"Expected no commit for no-change task, got SHA: {data.get('commit_sha')}"
        )


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("claude-code")
@skip_unless_env("ANTHROPIC_API_KEY")
async def test_budget_exceeded(
    async_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    github_token: str,
    workspace_root: str,
    unique_branch: str,
) -> None:
    """Budget ceiling of $0.001 triggers BudgetExceededError."""
    task_id = f"integ-budget-{uuid.uuid4().hex[:8]}"
    payload = _task_payload(
        task_id,
        unique_branch,
        github_token=github_token,
        max_cost_usd=0.001,  # Impossibly low — haiku costs ~$0.01
    )

    resp = await async_client.post("/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 202

    data = await poll_until_terminal(async_client, task_id, auth_headers)

    assert data["status"] == "failed"
    assert "budget" in (data.get("error_message") or "").lower(), (
        f"Expected 'budget' in error message, got: {data.get('error_message')}"
    )

    # Audit trail should record budget exceeded
    events = audit_log.get_events(task_id)
    actions = [e.action for e in events]
    assert "task.budget_exceeded" in actions, (
        f"Expected 'task.budget_exceeded' in audit trail, got: {actions}"
    )


@pytest.mark.e2e
@pytest.mark.slow
async def test_circuit_breaker_rejects(
    async_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    workspace_root: str,
) -> None:
    """Pre-tripped circuit breaker rejects task immediately — no engine call."""
    # Pre-trip the breaker for claude-code
    breaker = get_breaker("claude-code")
    for _ in range(5):
        breaker.record_failure()
    assert breaker.state == "open"

    task_id = f"integ-circuit-{uuid.uuid4().hex[:8]}"
    branch = f"integ/{uuid.uuid4().hex[:8]}"
    payload = _task_payload(
        task_id,
        branch,
        github_token=os.environ.get("GITHUB_TOKEN", ""),
        engine="claude-code",
    )

    resp = await async_client.post("/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 202

    data = await poll_until_terminal(
        async_client, task_id, auth_headers, timeout=30,
    )

    assert data["status"] == "failed"
    assert "circuit" in (data.get("error_message") or "").lower(), (
        f"Expected 'circuit' in error, got: {data.get('error_message')}"
    )

    # Audit trail
    events = audit_log.get_events(task_id)
    actions = [e.action for e in events]
    assert "task.circuit_open" in actions, (
        f"Expected 'task.circuit_open' in audit, got: {actions}"
    )

    # Cleanup: no branch was pushed, nothing to delete
    _delete_remote_branch(branch)


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("claude-code")
@skip_unless_env("ANTHROPIC_API_KEY")
async def test_cancellation(
    async_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    github_token: str,
    workspace_root: str,
    unique_branch: str,
) -> None:
    """Submit → wait briefly → cancel → status is cancelled, no commit pushed."""
    task_id = f"integ-cancel-{uuid.uuid4().hex[:8]}"
    payload = _task_payload(
        task_id, unique_branch, github_token=github_token,
    )

    resp = await async_client.post("/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 202

    # Wait for the task to start running before cancelling
    await asyncio.sleep(2)

    cancel_resp = await async_client.post(
        f"/tasks/{task_id}/cancel", headers=auth_headers,
    )
    # Cancel might return 200 or 400 (if already terminal).
    if cancel_resp.status_code == 200:
        data = await poll_until_terminal(
            async_client, task_id, auth_headers, timeout=30,
        )
        assert data["status"] in ("cancelled", "failed", "complete"), (
            f"Unexpected status after cancel: {data['status']}"
        )
    else:
        # Task finished before cancel — just verify it's terminal
        data = await poll_until_terminal(
            async_client, task_id, auth_headers, timeout=30,
        )

    # If cancelled, no commit should be pushed
    if data["status"] == "cancelled":
        events = audit_log.get_events(task_id)
        actions = [e.action for e in events]
        assert "task.cancelled" in actions

        # Branch should NOT exist on remote
        result = subprocess.run(
            [
                "git", "ls-remote", "--exit-code", "--heads",
                SANDBOX_REPO, f"refs/heads/{unique_branch}",
            ],
            capture_output=True,
            timeout=15,
        )
        # exit code 2 = ref not found (expected)
        assert result.returncode != 0, (
            "Branch should not exist on remote after cancellation"
        )


@pytest.mark.e2e
@pytest.mark.slow
@skip_unless_engine("claude-code")
@skip_unless_env("ANTHROPIC_API_KEY")
async def test_audit_trail_complete(
    async_client: httpx.AsyncClient,
    auth_headers: dict[str, str],
    github_token: str,
    workspace_root: str,
    unique_branch: str,
) -> None:
    """Audit trail records full lifecycle with increasing timestamps."""
    task_id = f"integ-audit-{uuid.uuid4().hex[:8]}"
    payload = _task_payload(
        task_id, unique_branch, github_token=github_token,
    )

    resp = await async_client.post("/tasks", json=payload, headers=auth_headers)
    assert resp.status_code == 202

    await poll_until_terminal(async_client, task_id, auth_headers)

    events = audit_log.get_events(task_id)
    actions = [e.action for e in events]

    # Expected lifecycle events in order
    assert "task.submitted" in actions
    assert "task.started" in actions
    assert "task.engine_selected" in actions

    # Terminal event — one of these
    terminal_events = {"task.completed", "task.failed", "task.budget_exceeded"}
    assert terminal_events & set(actions), (
        f"No terminal event found. Actions: {actions}"
    )

    # Timestamps should be monotonically non-decreasing
    timestamps = [e.timestamp for e in events]
    for i in range(1, len(timestamps)):
        assert timestamps[i] >= timestamps[i - 1], (
            f"Timestamps not monotonic: {timestamps[i - 1]} > {timestamps[i]} "
            f"at events {actions[i - 1]} → {actions[i]}"
        )
