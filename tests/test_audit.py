"""Tests for audit trail logging and NDJSON persistence."""

import json

from apps.runner.audit import AuditLog


def test_audit_records_events() -> None:
    audit = AuditLog()
    audit.record("task.submitted", task_id="t-1", engine="claude-code")
    audit.record("task.started", task_id="t-1")
    assert len(audit.events) == 2
    assert audit.events[0].action == "task.submitted"
    assert audit.events[0].metadata["engine"] == "claude-code"


def test_audit_filters_by_task() -> None:
    audit = AuditLog()
    audit.record("task.submitted", task_id="t-1")
    audit.record("task.submitted", task_id="t-2")
    audit.record("task.completed", task_id="t-1")
    t1_events = audit.get_events("t-1")
    assert len(t1_events) == 2


def test_audit_event_has_timestamp() -> None:
    audit = AuditLog()
    audit.record("task.submitted", task_id="t-1")
    assert audit.events[0].timestamp > 0


def test_audit_serializes_to_dict() -> None:
    audit = AuditLog()
    audit.record("task.submitted", task_id="t-1", engine="claude-code")
    d = audit.events[0].to_dict()
    assert d["action"] == "task.submitted"
    assert d["task_id"] == "t-1"
    assert "timestamp" in d


def test_audit_clear_removes_all() -> None:
    audit = AuditLog()
    audit.record("task.submitted", task_id="t-1")
    audit.record("task.submitted", task_id="t-2")
    audit.clear()
    assert len(audit.events) == 0


def test_audit_get_events_returns_empty_for_unknown() -> None:
    audit = AuditLog()
    assert audit.get_events("nonexistent") == []


# ── Persistence tests ─────────────────────────────────────────────────────


def test_audit_persists_to_ndjson_file(tmp_path) -> None:
    """Events are appended as NDJSON lines when persist_path is set."""
    log_file = tmp_path / "audit.ndjson"
    audit = AuditLog(persist_path=log_file)
    audit.record("task.submitted", task_id="t-1", engine="claude-code")
    audit.record("task.started", task_id="t-1")

    lines = log_file.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["action"] == "task.submitted"
    assert first["task_id"] == "t-1"
    assert first["engine"] == "claude-code"
    assert "timestamp" in first


def test_audit_load_from_file(tmp_path) -> None:
    """load_from_file() restores events from NDJSON into memory."""
    log_file = tmp_path / "audit.ndjson"
    # Write directly
    audit_writer = AuditLog(persist_path=log_file)
    audit_writer.record("task.submitted", task_id="t-1", engine="aider")
    audit_writer.record("task.completed", task_id="t-1", cost_usd=0.42)

    # Load into a fresh instance
    audit_reader = AuditLog(persist_path=log_file)
    count = audit_reader.load_from_file()
    assert count == 2
    assert len(audit_reader.events) == 2
    assert audit_reader.events[0].action == "task.submitted"
    assert audit_reader.events[1].metadata["cost_usd"] == 0.42


def test_audit_load_from_nonexistent_file(tmp_path) -> None:
    """load_from_file() returns 0 when file doesn't exist yet."""
    log_file = tmp_path / "missing.ndjson"
    audit = AuditLog(persist_path=log_file)
    count = audit.load_from_file()
    assert count == 0
    assert len(audit.events) == 0


def test_audit_load_skips_corrupt_lines(tmp_path) -> None:
    """Corrupt NDJSON lines are skipped gracefully."""
    log_file = tmp_path / "audit.ndjson"
    log_file.write_text(
        json.dumps({"action": "task.submitted", "task_id": "t-1", "timestamp": 1.0})
        + "\n"
        + "not valid json\n"
        + json.dumps({"action": "task.completed", "task_id": "t-1", "timestamp": 2.0})
        + "\n"
    )
    audit = AuditLog(persist_path=log_file)
    count = audit.load_from_file()
    assert count == 2  # corrupt line skipped


def test_audit_no_persist_path_by_default() -> None:
    """Without persist_path, no file is written."""
    audit = AuditLog()
    assert audit.persist_path is None
    audit.record("task.submitted", task_id="t-1")
    # No file ops — just in-memory


def test_audit_persist_path_from_env(tmp_path, monkeypatch) -> None:
    """persist_path can be set via LAILATOV_AUDIT_LOG env var."""
    log_file = tmp_path / "env_audit.ndjson"
    monkeypatch.setenv("LAILATOV_AUDIT_LOG", str(log_file))
    audit = AuditLog()
    assert audit.persist_path == log_file
    audit.record("task.submitted", task_id="t-1")
    assert log_file.exists()


def test_audit_constructor_path_overrides_env(tmp_path, monkeypatch) -> None:
    """Explicit persist_path in constructor overrides env var."""
    env_file = tmp_path / "env.ndjson"
    constructor_file = tmp_path / "explicit.ndjson"
    monkeypatch.setenv("LAILATOV_AUDIT_LOG", str(env_file))
    audit = AuditLog(persist_path=constructor_file)
    assert audit.persist_path == constructor_file


def test_audit_load_raises_without_persist_path() -> None:
    """load_from_file() raises ValueError if no persist_path configured."""
    import pytest

    audit = AuditLog()
    with pytest.raises(ValueError, match="persist_path"):
        audit.load_from_file()


def test_audit_creates_parent_dirs(tmp_path) -> None:
    """persist_path parent directories are created automatically."""
    log_file = tmp_path / "deep" / "nested" / "audit.ndjson"
    audit = AuditLog(persist_path=log_file)
    audit.record("task.submitted", task_id="t-1")
    assert log_file.exists()
