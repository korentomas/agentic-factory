"""SWE-bench evaluation harness for benchmarking agent engines.

Provides dataclasses for benchmark instances and results, plus a
BenchmarkSuite that tracks pass rates, costs, and can persist
results to JSON.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class BenchmarkInstance:
    """A single SWE-bench evaluation instance.

    Each instance represents a real GitHub issue with a known fix.
    The agent attempts to solve the issue starting from ``base_commit``,
    and correctness is verified by applying ``test_patch`` after the
    agent's changes.

    Attributes:
        instance_id:     Unique identifier (e.g. "django__django-12345").
        repo:            GitHub repo (e.g. "django/django").
        base_commit:     Commit SHA to start from.
        issue_text:      The issue description used as agent prompt.
        test_patch:      Patch to apply after agent changes for evaluation.
        expected_status: What the test should report after applying the patch.
    """

    instance_id: str
    repo: str
    base_commit: str
    issue_text: str
    test_patch: str
    expected_status: str = "pass"


@dataclass(frozen=True)
class BenchmarkResult:
    """Outcome of running an agent engine on a single benchmark instance.

    Attributes:
        instance_id:   Matches the BenchmarkInstance.
        engine:        Engine that ran (e.g. "claude-code", "aider").
        model:         Model used (e.g. "claude-sonnet-4-6").
        status:        Terminal status — "pass", "fail", "error", or "timeout".
        duration_ms:   Wall-clock execution time in milliseconds.
        cost_usd:      LLM API cost for this instance.
        error_message: Error details if status is "error" or "timeout".
    """

    instance_id: str
    engine: str
    model: str
    status: str
    duration_ms: int = 0
    cost_usd: float = 0.0
    error_message: str | None = None


class BenchmarkSuite:
    """Manages a collection of benchmark instances and their results.

    Tracks pass rates, cumulative costs, and supports JSON persistence
    for reproducible evaluation runs.

    Args:
        instances: Initial list of benchmark instances to evaluate.
    """

    def __init__(self, instances: list[BenchmarkInstance] | None = None) -> None:
        self.instances: list[BenchmarkInstance] = instances or []
        self.results: list[BenchmarkResult] = []

    def add_result(self, result: BenchmarkResult) -> None:
        """Append a result to the suite.

        Args:
            result: The benchmark result to record.
        """
        self.results.append(result)
        logger.info(
            "benchmark.result_added",
            instance_id=result.instance_id,
            status=result.status,
            engine=result.engine,
        )

    def pass_at_1(self) -> float:
        """Fraction of instances that passed on the first attempt.

        Returns:
            A float between 0.0 and 1.0, or 0.0 if no results exist.
        """
        if not self.results:
            return 0.0
        passed = sum(1 for r in self.results if r.status == "pass")
        return passed / len(self.results)

    def total_cost(self) -> float:
        """Sum of all result costs in USD.

        Returns:
            Cumulative cost across all recorded results.
        """
        return sum(r.cost_usd for r in self.results)

    def summary(self) -> dict[str, object]:
        """Summary statistics for the benchmark run.

        Returns:
            Dictionary with keys: pass_rate, total, passed, failed,
            errors, total_cost.
        """
        passed = sum(1 for r in self.results if r.status == "pass")
        failed = sum(1 for r in self.results if r.status == "fail")
        errors = sum(
            1 for r in self.results if r.status in ("error", "timeout")
        )
        total = len(self.results)
        return {
            "pass_rate": self.pass_at_1(),
            "total": total,
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "total_cost": self.total_cost(),
        }

    def save_results(self, path: Path) -> None:
        """Write all results as a JSON array to disk.

        Args:
            path: File path to write the JSON output.
        """
        data = [asdict(r) for r in self.results]
        path.write_text(json.dumps(data, indent=2))
        logger.info(
            "benchmark.results_saved",
            path=str(path),
            count=len(self.results),
        )

    def load_instances(self, path: Path) -> None:
        """Load benchmark instances from a JSON file.

        The file should contain a JSON array of objects with keys
        matching BenchmarkInstance fields.

        Args:
            path: File path to read instances from.
        """
        raw = json.loads(path.read_text())
        for item in raw:
            self.instances.append(BenchmarkInstance(**item))
        logger.info(
            "benchmark.instances_loaded",
            path=str(path),
            count=len(raw),
        )
