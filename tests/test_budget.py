"""Tests for cost budget enforcement."""

import pytest

from apps.runner.budget import BudgetExceededError, BudgetTracker


def test_budget_allows_within_limit() -> None:
    bt = BudgetTracker(max_cost_usd=10.0)
    bt.record_cost(5.0)
    assert bt.remaining == 5.0
    bt.check()


def test_budget_raises_when_exceeded() -> None:
    bt = BudgetTracker(max_cost_usd=1.0)
    bt.record_cost(1.5)
    with pytest.raises(BudgetExceededError):
        bt.check()


def test_budget_unlimited_when_zero() -> None:
    bt = BudgetTracker(max_cost_usd=0.0)
    bt.record_cost(1000.0)
    bt.check()


def test_budget_tracks_cumulative_cost() -> None:
    bt = BudgetTracker(max_cost_usd=5.0)
    bt.record_cost(2.0)
    bt.record_cost(2.0)
    assert bt.spent == 4.0
    assert bt.remaining == 1.0
    bt.record_cost(2.0)
    with pytest.raises(BudgetExceededError):
        bt.check()


def test_budget_error_has_metadata() -> None:
    err = BudgetExceededError(spent=5.0, limit=3.0)
    assert err.spent == 5.0
    assert err.limit == 3.0
    assert "$5.0000" in str(err)


def test_remaining_returns_inf_when_unlimited() -> None:
    bt = BudgetTracker(max_cost_usd=0.0)
    assert bt.remaining == float("inf")


def test_remaining_never_negative() -> None:
    bt = BudgetTracker(max_cost_usd=1.0)
    bt.record_cost(5.0)
    assert bt.remaining == 0.0
