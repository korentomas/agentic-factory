"""Audit trail for agent task lifecycle events.

Records structured events for every significant action:
submit, start, engine selection, commit, push, cancel, complete, fail.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class AuditEvent:
    """A single audit event."""

    action: str
    task_id: str
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "action": self.action,
            "task_id": self.task_id,
            "timestamp": self.timestamp,
            **self.metadata,
        }


class AuditLog:
    """In-memory audit log for task lifecycle events.

    Thread-safe for single-process async use.
    Future: persist to database or structured log file.
    """

    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    def record(self, action: str, *, task_id: str, **metadata: object) -> None:
        """Record an audit event."""
        event = AuditEvent(
            action=action,
            task_id=task_id,
            timestamp=time.time(),
            metadata=metadata,
        )
        self.events.append(event)
        logger.info("audit", **event.to_dict())

    def get_events(self, task_id: str) -> list[AuditEvent]:
        """Get all events for a task."""
        return [e for e in self.events if e.task_id == task_id]

    def clear(self) -> None:
        """Clear all events."""
        self.events.clear()
