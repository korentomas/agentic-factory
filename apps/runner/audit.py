"""Audit trail for agent task lifecycle events.

Records structured events for every significant action:
submit, start, engine selection, commit, push, cancel, complete, fail.

Events are kept in-memory for fast queries and optionally persisted
to an NDJSON file (one JSON object per line) for durability.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger()


def _get_env(key: str, default: str = "") -> str:
    """Read env var at call time."""
    return os.getenv(key, default)


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
    """Audit log for task lifecycle events with optional NDJSON persistence.

    Thread-safe for single-process async use.

    When ``persist_path`` is provided, every event is appended as a JSON
    line to that file. Events are also kept in memory for fast queries.

    Args:
        persist_path: Optional path to an NDJSON file for durable storage.
                      Set via ``LAILATOV_AUDIT_LOG`` env var or constructor arg.
    """

    def __init__(self, persist_path: Path | str | None = None) -> None:
        self.events: list[AuditEvent] = []
        env_path = _get_env("LAILATOV_AUDIT_LOG")
        if persist_path is not None:
            self._persist_path: Path | None = Path(persist_path)
        elif env_path:
            self._persist_path = Path(env_path)
        else:
            self._persist_path = None

        if self._persist_path:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def persist_path(self) -> Path | None:
        """Return the configured persistence path, if any."""
        return self._persist_path

    def record(self, action: str, *, task_id: str, **metadata: object) -> None:
        """Record an audit event.

        Appends to in-memory list and, if configured, writes to NDJSON file.
        """
        event = AuditEvent(
            action=action,
            task_id=task_id,
            timestamp=time.time(),
            metadata=metadata,
        )
        self.events.append(event)
        logger.info("audit", **event.to_dict())

        if self._persist_path:
            self._append_to_file(event)

    def get_events(self, task_id: str) -> list[AuditEvent]:
        """Get all events for a task."""
        return [e for e in self.events if e.task_id == task_id]

    def clear(self) -> None:
        """Clear all in-memory events."""
        self.events.clear()

    def load_from_file(self) -> int:
        """Load events from the NDJSON file into memory.

        Returns:
            Number of events loaded.

        Raises:
            ValueError: If no persist_path is configured.
        """
        if not self._persist_path:
            msg = "No persist_path configured"
            raise ValueError(msg)

        if not self._persist_path.exists():
            return 0

        count = 0
        for line in self._persist_path.read_text().splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                event = AuditEvent(
                    action=data["action"],
                    task_id=data["task_id"],
                    timestamp=data["timestamp"],
                    metadata={
                        k: v
                        for k, v in data.items()
                        if k not in ("action", "task_id", "timestamp")
                    },
                )
                self.events.append(event)
                count += 1
            except (json.JSONDecodeError, KeyError):
                logger.warning("audit.load.skip_line", line=line[:100])
                continue
        return count

    def _append_to_file(self, event: AuditEvent) -> None:
        """Append a single event as NDJSON to the persist file."""
        try:
            with self._persist_path.open("a") as f:  # type: ignore[union-attr]
                f.write(json.dumps(event.to_dict(), default=str) + "\n")
        except OSError:
            logger.warning("audit.persist.failed", path=str(self._persist_path))
