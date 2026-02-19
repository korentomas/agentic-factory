"""Tests for apps.runner.benchmark — SWE-bench evaluation harness."""

from __future__ import annotations

import json

import pytest

from apps.runner.benchmark import BenchmarkInstance, BenchmarkResult, BenchmarkSuite


def _make_instance(instance_id: str = "django__django-12345") -> BenchmarkInstance:
    """Helper to create a BenchmarkInstance with sensible defaults."""
    return BenchmarkInstance(
        instance_id=instance_id,
        repo="django/django",
        base_commit="abc123",
        issue_text="Fix the ORM bug",
        test_patch="diff --git a/test.py ...",
    )


def _make_result(
    instance_id: str = "django__django-12345",
    status: str = "pass",
    cost_usd: float = 0.10,
) -> BenchmarkResult:
    """Helper to create a BenchmarkResult with sensible defaults."""
    return BenchmarkResult(
        instance_id=instance_id,
        engine="claude-code",
        model="claude-sonnet-4-6",
        status=status,
        duration_ms=5000,
        cost_usd=cost_usd,
    )


class TestBenchmarkInstance:
    """Tests for BenchmarkInstance frozen dataclass."""

    def test_frozen(self) -> None:
        instance = _make_instance()
        with pytest.raises(AttributeError):
            instance.instance_id = "changed"  # type: ignore[misc]

    def test_default_expected_status(self) -> None:
        instance = _make_instance()
        assert instance.expected_status == "pass"

    def test_fields_set(self) -> None:
        instance = _make_instance()
        assert instance.instance_id == "django__django-12345"
        assert instance.repo == "django/django"
        assert instance.base_commit == "abc123"
        assert instance.issue_text == "Fix the ORM bug"
        assert instance.test_patch == "diff --git a/test.py ..."


class TestBenchmarkResult:
    """Tests for BenchmarkResult frozen dataclass."""

    def test_frozen(self) -> None:
        result = _make_result()
        with pytest.raises(AttributeError):
            result.status = "fail"  # type: ignore[misc]

    def test_defaults(self) -> None:
        result = BenchmarkResult(
            instance_id="t1",
            engine="aider",
            model="gpt-4.1",
            status="pass",
        )
        assert result.duration_ms == 0
        assert result.cost_usd == 0.0
        assert result.error_message is None

    def test_error_result(self) -> None:
        result = BenchmarkResult(
            instance_id="t1",
            engine="claude-code",
            model="claude-sonnet-4-6",
            status="error",
            error_message="Subprocess crashed",
        )
        assert result.status == "error"
        assert result.error_message == "Subprocess crashed"


class TestBenchmarkSuite:
    """Tests for BenchmarkSuite collection logic."""

    def test_add_result_appends(self) -> None:
        suite = BenchmarkSuite()
        result = _make_result()
        suite.add_result(result)
        assert len(suite.results) == 1
        assert suite.results[0] is result

    def test_pass_at_1_all_passing(self) -> None:
        suite = BenchmarkSuite()
        for i in range(5):
            suite.add_result(_make_result(instance_id=f"inst-{i}", status="pass"))
        assert suite.pass_at_1() == 1.0

    def test_pass_at_1_mixed_results(self) -> None:
        suite = BenchmarkSuite()
        suite.add_result(_make_result(instance_id="a", status="pass"))
        suite.add_result(_make_result(instance_id="b", status="fail"))
        suite.add_result(_make_result(instance_id="c", status="pass"))
        suite.add_result(_make_result(instance_id="d", status="error"))
        assert suite.pass_at_1() == 0.5

    def test_pass_at_1_empty_suite(self) -> None:
        suite = BenchmarkSuite()
        assert suite.pass_at_1() == 0.0

    def test_total_cost_sums_correctly(self) -> None:
        suite = BenchmarkSuite()
        suite.add_result(_make_result(instance_id="a", cost_usd=0.10))
        suite.add_result(_make_result(instance_id="b", cost_usd=0.25))
        suite.add_result(_make_result(instance_id="c", cost_usd=0.05))
        assert suite.total_cost() == pytest.approx(0.40)

    def test_summary_returns_expected_shape(self) -> None:
        suite = BenchmarkSuite()
        suite.add_result(_make_result(instance_id="a", status="pass", cost_usd=0.10))
        suite.add_result(_make_result(instance_id="b", status="fail", cost_usd=0.20))
        suite.add_result(_make_result(instance_id="c", status="error", cost_usd=0.05))
        suite.add_result(_make_result(instance_id="d", status="timeout", cost_usd=0.15))

        summary = suite.summary()

        assert summary["total"] == 4
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["errors"] == 2  # error + timeout
        assert summary["pass_rate"] == pytest.approx(0.25)
        assert summary["total_cost"] == pytest.approx(0.50)

    def test_save_results_writes_valid_json(self, tmp_path: object) -> None:
        suite = BenchmarkSuite()
        suite.add_result(_make_result(instance_id="a", status="pass", cost_usd=0.10))
        suite.add_result(_make_result(instance_id="b", status="fail", cost_usd=0.20))

        from pathlib import Path

        assert isinstance(tmp_path, Path)
        out = tmp_path / "results.json"
        suite.save_results(out)

        data = json.loads(out.read_text())
        assert isinstance(data, list)
        assert len(data) == 2
        assert data[0]["instance_id"] == "a"
        assert data[0]["status"] == "pass"
        assert data[1]["instance_id"] == "b"
        assert data[1]["status"] == "fail"

    def test_load_instances_from_json(self, tmp_path: object) -> None:
        from pathlib import Path

        assert isinstance(tmp_path, Path)

        instances_data = [
            {
                "instance_id": "django__django-12345",
                "repo": "django/django",
                "base_commit": "abc123",
                "issue_text": "Fix ORM",
                "test_patch": "diff ...",
            },
            {
                "instance_id": "flask__flask-6789",
                "repo": "pallets/flask",
                "base_commit": "def456",
                "issue_text": "Fix routing",
                "test_patch": "diff ...",
                "expected_status": "pass",
            },
        ]
        path = tmp_path / "instances.json"
        path.write_text(json.dumps(instances_data))

        suite = BenchmarkSuite()
        suite.load_instances(path)

        assert len(suite.instances) == 2
        assert suite.instances[0].instance_id == "django__django-12345"
        assert suite.instances[0].repo == "django/django"
        assert suite.instances[1].instance_id == "flask__flask-6789"
        assert suite.instances[1].expected_status == "pass"

    def test_suite_initialized_with_instances(self) -> None:
        instances = [_make_instance("a"), _make_instance("b")]
        suite = BenchmarkSuite(instances=instances)
        assert len(suite.instances) == 2
        assert suite.instances[0].instance_id == "a"

    def test_total_cost_empty_suite(self) -> None:
        suite = BenchmarkSuite()
        assert suite.total_cost() == 0.0

    def test_summary_empty_suite(self) -> None:
        suite = BenchmarkSuite()
        summary = suite.summary()
        assert summary["total"] == 0
        assert summary["passed"] == 0
        assert summary["failed"] == 0
        assert summary["errors"] == 0
        assert summary["pass_rate"] == 0.0
        assert summary["total_cost"] == 0.0
