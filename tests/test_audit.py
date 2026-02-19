"""Tests for audit trail logging."""

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
