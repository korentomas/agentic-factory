"""Cost budget enforcement for agent tasks.

Tracks cumulative LLM API spend and raises when a per-task
budget ceiling is exceeded.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger()


class BudgetExceededError(Exception):
    """Raised when a task exceeds its cost budget."""

    def __init__(self, spent: float, limit: float) -> None:
        self.spent = spent
        self.limit = limit
        super().__init__(
            f"Cost budget exceeded: ${spent:.4f} spent, "
            f"${limit:.4f} limit"
        )


class BudgetTracker:
    """Tracks cumulative cost and enforces a ceiling.

    Args:
        max_cost_usd: Maximum allowed cost. 0.0 means unlimited.
    """

    def __init__(self, max_cost_usd: float = 0.0) -> None:
        self.max_cost_usd = max_cost_usd
        self.spent: float = 0.0

    @property
    def remaining(self) -> float:
        """Remaining budget. Returns float('inf') if unlimited."""
        if self.max_cost_usd <= 0:
            return float("inf")
        return max(0.0, self.max_cost_usd - self.spent)

    def record_cost(self, cost_usd: float) -> None:
        """Record a cost increment."""
        self.spent += cost_usd

    def check(self) -> None:
        """Raise BudgetExceededError if budget is exceeded."""
        if self.max_cost_usd > 0 and self.spent > self.max_cost_usd:
            logger.warning(
                "budget.exceeded",
                spent=self.spent,
                limit=self.max_cost_usd,
            )
            raise BudgetExceededError(self.spent, self.max_cost_usd)
