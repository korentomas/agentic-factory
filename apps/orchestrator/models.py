"""
AgentTask — the central domain type for AgentFactory.

Design: parse-at-boundary pattern.
See: https://lexi-lambda.github.io/blog/2019/11/05/parse-don-t-validate/

If you have an AgentTask, it is guaranteed valid. Construction IS validation.
All downstream code takes AgentTask and trusts it — no redundant checks.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Literal

# ── Risk tier heuristics ──────────────────────────────────────────────────────
# These keywords in a ticket title/description signal HIGH risk.
# Tune this for your codebase.
HIGH_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        "auth",
        "authentication",
        "authorization",
        "tenant",
        "tenancy",
        "security",
        "permission",
        "migration",
        "schema",
        "admin",
        "password",
        "token",
        "jwt",
        "oauth",
        "credential",
        "secret",
        "encrypt",
        "cypher",
        "neo4j",
        "database",
        "sql",
        "ddl",
    }
)

# These keywords signal MEDIUM risk.
MEDIUM_RISK_KEYWORDS: frozenset[str] = frozenset(
    {
        "api",
        "endpoint",
        "route",
        "service",
        "integration",
        "webhook",
        "billing",
        "payment",
        "import",
        "export",
        "sync",
    }
)

# Description length above which we treat the task as high-complexity.
# Long descriptions imply multi-component work that benefits from a PLANS.md.
COMPLEXITY_HIGH_THRESHOLD = 500


@dataclass(frozen=True)
class AgentTask:
    """
    A fully parsed and validated agent task.

    Frozen (immutable after creation) because tasks should not mutate once
    parsed from the webhook boundary. Any modification creates a new instance.

    Fields:
        clickup_task_id: The ClickUp task identifier (e.g. "abc123def")
        title:           Task title, stripped of whitespace. Never empty.
        description:     Full task description. May be empty string.
        correlation_id:  UUID for correlating webhook → dispatch → callback.
        risk_tier:       Risk level inferred from task content.
        complexity:      Complexity level — drives plan-first protocol.

    Do not instantiate directly in application code. Use from_clickup_payload().
    """

    clickup_task_id: str
    title: str
    description: str
    correlation_id: str
    risk_tier: Literal["high", "medium", "low"]
    complexity: Literal["high", "standard"]
    # Branch name — derived, not user-supplied
    branch: str = field(init=False)

    def __post_init__(self) -> None:
        # Compute derived field (frozen dataclass workaround)
        object.__setattr__(
            self,
            "branch",
            f"agent/cu-{self.clickup_task_id}",
        )

    @classmethod
    def from_clickup_payload(
        cls,
        task_id: str,
        task_details: dict[str, object],
        *,
        correlation_id: str | None = None,
    ) -> "AgentTask":
        """
        Parse and validate a ClickUp task payload into an AgentTask.

        This is the ONLY way AgentTask should be created from external data.
        All validation happens here. Raises ValueError with clear messages
        so callers can log/reject rather than propagate malformed state.

        Args:
            task_id: The ClickUp task ID from the webhook payload.
            task_details: The full task object from GET /api/v2/task/{id}.
            correlation_id: Optional correlation UUID. Auto-generated if absent.

        Raises:
            ValueError: If the task is missing required fields or malformed.
        """
        # ── Validate task_id ──────────────────────────────────────────────────
        task_id = task_id.strip() if isinstance(task_id, str) else ""
        if not task_id:
            raise ValueError("Missing or empty task_id in webhook payload")

        if not re.match(r"^[a-zA-Z0-9_\-]+$", task_id):
            raise ValueError(
                f"task_id contains invalid characters: {task_id!r}. "
                "Expected alphanumeric, hyphens, underscores only."
            )

        # ── Extract and validate title ────────────────────────────────────────
        raw_title = task_details.get("name", "")
        title = str(raw_title).strip() if raw_title is not None else ""
        if not title:
            raise ValueError(
                f"Task {task_id!r} has no title (name field is empty or missing)"
            )

        # ── Extract description ───────────────────────────────────────────────
        raw_desc = task_details.get("description", "")
        description = str(raw_desc).strip() if raw_desc is not None else ""

        # ── Infer risk tier ───────────────────────────────────────────────────
        combined_text = f"{title} {description}".lower()
        # Tokenize on word boundaries
        words: set[str] = set(re.findall(r"\b[a-z]+\b", combined_text))

        risk_tier: Literal["high", "medium", "low"]
        if words & HIGH_RISK_KEYWORDS:
            risk_tier = "high"
        elif words & MEDIUM_RISK_KEYWORDS:
            risk_tier = "medium"
        else:
            risk_tier = "low"

        # ── Infer complexity ──────────────────────────────────────────────────
        complexity: Literal["high", "standard"]
        if len(description) > COMPLEXITY_HIGH_THRESHOLD:
            complexity = "high"
        else:
            complexity = "standard"

        # ── Correlation ID ────────────────────────────────────────────────────
        if correlation_id is None:
            correlation_id = str(uuid.uuid4())
        elif not _is_valid_uuid(correlation_id):
            # Don't hard-fail — just generate a new one and log
            correlation_id = str(uuid.uuid4())

        return cls(
            clickup_task_id=task_id,
            title=title,
            description=description,
            correlation_id=correlation_id,
            risk_tier=risk_tier,
            complexity=complexity,
        )

    def to_dispatch_payload(self) -> dict[str, str]:
        """
        Serialize to the format expected by GitHub Actions repository_dispatch.

        This is the client_payload sent to:
          POST /repos/{owner}/{repo}/dispatches
        """
        return {
            "clickup_task_id": self.clickup_task_id,
            "title": self.title,
            "description": self.description,
            "correlation_id": self.correlation_id,
            "risk_tier": self.risk_tier,
            "complexity": self.complexity,
            "branch": self.branch,
        }

    def __repr__(self) -> str:
        return (
            f"AgentTask("
            f"id={self.clickup_task_id!r}, "
            f"title={self.title[:50]!r}, "
            f"risk={self.risk_tier}, "
            f"complexity={self.complexity}"
            f")"
        )


def _is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False
