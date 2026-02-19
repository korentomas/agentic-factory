"""Tests for circuit breaker pattern."""

import time

from apps.runner.circuit_breaker import CircuitBreaker, CircuitOpenError


def test_circuit_starts_closed() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    assert cb.state == "closed"
    assert cb.allow_request()


def test_circuit_opens_after_threshold() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "open"
    assert not cb.allow_request()


def test_circuit_transitions_to_half_open() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "open"
    cb._opened_at = time.monotonic() - 2
    assert cb.state == "half_open"
    assert cb.allow_request()


def test_circuit_closes_on_success_in_half_open() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    cb._opened_at = time.monotonic() - 2
    assert cb.state == "half_open"
    cb.record_success()
    assert cb.state == "closed"


def test_circuit_reopens_on_failure_in_half_open() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    cb._opened_at = time.monotonic() - 2
    assert cb.state == "half_open"
    cb.record_failure()
    assert cb.state == "open"


def test_success_resets_failure_count() -> None:
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=60)
    cb.record_failure()
    cb.record_failure()
    cb.record_success()
    assert cb._failure_count == 0
    assert cb.state == "closed"


def test_circuit_open_error_has_metadata() -> None:
    err = CircuitOpenError(engine="claude-code", retry_after=300)
    assert err.engine == "claude-code"
    assert err.retry_after == 300
    assert "claude-code" in str(err)
