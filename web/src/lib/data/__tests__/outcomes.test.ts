import { describe, it, expect, vi, beforeEach } from "vitest";
import type { AgentOutcome } from "../types";

const { mockReadFile } = vi.hoisted(() => ({
  mockReadFile: vi.fn(),
}));

// Mock fs module before importing the module under test
vi.mock("fs", () => {
  const mockPromises = { readFile: mockReadFile };
  return {
    default: { promises: mockPromises },
    promises: mockPromises,
  };
});

import {
  loadOutcomes,
  computeStats,
  computeEngineBreakdown,
  computeModelBreakdown,
  computeCheckHealth,
  computeRiskBreakdown,
  computeFileHotspots,
} from "../outcomes";

/** Helper to create a realistic AgentOutcome for testing. */
function makeOutcome(overrides: Partial<AgentOutcome> = {}): AgentOutcome {
  return {
    outcome: "clean",
    pr_url: "https://github.com/korentomas/agentic-factory/pull/1",
    pr_number: 1,
    branch: "agent/task-1",
    risk_tier: "medium",
    checks: {
      gate: "success",
      tests: "success",
      review: "success",
      spec_audit: "success",
    },
    files_changed: ["src/main.py"],
    review_findings: [],
    run_id: "run-001",
    timestamp: new Date().toISOString(),
    model: "claude-sonnet-4-6",
    cost_usd: 0.05,
    duration_ms: 120000,
    engine: "claude-code",
    num_turns: 3,
    ...overrides,
  };
}

describe("loadOutcomes", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("parses valid JSONL with multiple lines", async () => {
    const line1 = JSON.stringify(makeOutcome({ pr_number: 1 }));
    const line2 = JSON.stringify(makeOutcome({ pr_number: 2 }));
    mockReadFile.mockResolvedValue(`${line1}\n${line2}\n`);

    const outcomes = await loadOutcomes();
    expect(outcomes).toHaveLength(2);
    expect(outcomes[0].pr_number).toBe(1);
    expect(outcomes[1].pr_number).toBe(2);
  });

  it("handles a single-line JSONL file", async () => {
    const line = JSON.stringify(makeOutcome({ pr_number: 42 }));
    mockReadFile.mockResolvedValue(line);

    const outcomes = await loadOutcomes();
    expect(outcomes).toHaveLength(1);
    expect(outcomes[0].pr_number).toBe(42);
  });

  it("skips blank lines in JSONL", async () => {
    const line1 = JSON.stringify(makeOutcome({ pr_number: 1 }));
    const line2 = JSON.stringify(makeOutcome({ pr_number: 2 }));
    mockReadFile.mockResolvedValue(`${line1}\n\n\n${line2}\n`);

    const outcomes = await loadOutcomes();
    expect(outcomes).toHaveLength(2);
  });

  it("returns empty array for an empty file", async () => {
    mockReadFile.mockResolvedValue("");

    const outcomes = await loadOutcomes();
    expect(outcomes).toEqual([]);
  });

  it("returns empty array when the file is missing", async () => {
    mockReadFile.mockRejectedValue(
      new Error("ENOENT: no such file or directory")
    );

    const outcomes = await loadOutcomes();
    expect(outcomes).toEqual([]);
  });

  it("returns empty array on read permission error", async () => {
    mockReadFile.mockRejectedValue(
      new Error("EACCES: permission denied")
    );

    const outcomes = await loadOutcomes();
    expect(outcomes).toEqual([]);
  });
});

describe("computeStats", () => {
  it("computes stats for mixed outcomes", () => {
    const outcomes = [
      makeOutcome({ outcome: "clean", cost_usd: 0.10, duration_ms: 100000 }),
      makeOutcome({ outcome: "tests-failed", cost_usd: 0.05, duration_ms: 200000 }),
      makeOutcome({ outcome: "clean", cost_usd: 0.15, duration_ms: 150000 }),
    ];

    const stats = computeStats(outcomes);
    expect(stats.totalTasks).toBe(3);
    expect(stats.prsClean).toBe(2);
    expect(stats.prsFailed).toBe(1);
    expect(stats.successRate).toBeCloseTo(2 / 3, 5);
    expect(stats.totalCost).toBeCloseTo(0.30, 5);
    expect(stats.avgDurationMs).toBeCloseTo(150000, 0);
  });

  it("returns zero values for empty array", () => {
    const stats = computeStats([]);
    expect(stats.totalTasks).toBe(0);
    expect(stats.prsClean).toBe(0);
    expect(stats.prsFailed).toBe(0);
    expect(stats.successRate).toBe(0);
    expect(stats.totalCost).toBe(0);
    expect(stats.costThisMonth).toBe(0);
    expect(stats.avgDurationMs).toBe(0);
  });

  it("returns 100% success rate when all outcomes are clean", () => {
    const outcomes = [
      makeOutcome({ outcome: "clean" }),
      makeOutcome({ outcome: "clean" }),
    ];
    const stats = computeStats(outcomes);
    expect(stats.successRate).toBe(1);
    expect(stats.prsClean).toBe(2);
    expect(stats.prsFailed).toBe(0);
  });

  it("returns 0% success rate when all outcomes failed", () => {
    const outcomes = [
      makeOutcome({ outcome: "tests-failed" }),
      makeOutcome({ outcome: "review-failed" }),
      makeOutcome({ outcome: "blocked" }),
    ];
    const stats = computeStats(outcomes);
    expect(stats.successRate).toBe(0);
    expect(stats.prsClean).toBe(0);
    expect(stats.prsFailed).toBe(3);
  });

  it("aggregates cost correctly including null values", () => {
    const outcomes = [
      makeOutcome({ cost_usd: 0.10 }),
      makeOutcome({ cost_usd: undefined }),
      makeOutcome({ cost_usd: 0.20 }),
    ];
    const stats = computeStats(outcomes);
    expect(stats.totalCost).toBeCloseTo(0.30, 5);
  });

  it("counts tasks this month correctly", () => {
    const now = new Date();
    const thisMonth = new Date(now.getFullYear(), now.getMonth(), 15).toISOString();
    const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 15).toISOString();

    const outcomes = [
      makeOutcome({ timestamp: thisMonth }),
      makeOutcome({ timestamp: lastMonth }),
      makeOutcome({ timestamp: thisMonth }),
    ];
    const stats = computeStats(outcomes);
    expect(stats.tasksThisMonth).toBe(2);
  });

  it("computes monthly cost from this-month outcomes only", () => {
    const now = new Date();
    const thisMonth = new Date(now.getFullYear(), now.getMonth(), 10).toISOString();
    const lastMonth = new Date(now.getFullYear(), now.getMonth() - 1, 10).toISOString();

    const outcomes = [
      makeOutcome({ timestamp: thisMonth, cost_usd: 0.50 }),
      makeOutcome({ timestamp: lastMonth, cost_usd: 1.00 }),
    ];
    const stats = computeStats(outcomes);
    expect(stats.costThisMonth).toBeCloseTo(0.50, 5);
    expect(stats.totalCost).toBeCloseTo(1.50, 5);
  });

  it("handles outcomes with no duration_ms", () => {
    const outcomes = [
      makeOutcome({ duration_ms: undefined }),
      makeOutcome({ duration_ms: undefined }),
    ];
    const stats = computeStats(outcomes);
    expect(stats.avgDurationMs).toBe(0);
  });
});

describe("computeEngineBreakdown", () => {
  it("groups outcomes by engine", () => {
    const outcomes = [
      makeOutcome({ engine: "claude-code", outcome: "clean" }),
      makeOutcome({ engine: "claude-code", outcome: "tests-failed" }),
      makeOutcome({ engine: "codex", outcome: "clean" }),
    ];
    const breakdown = computeEngineBreakdown(outcomes);
    expect(breakdown).toHaveLength(2);

    const cc = breakdown.find((b) => b.engine === "claude-code")!;
    expect(cc.count).toBe(2);
    expect(cc.successCount).toBe(1);
    expect(cc.failureCount).toBe(1);
    expect(cc.successRate).toBe(0.5);

    const codex = breakdown.find((b) => b.engine === "codex")!;
    expect(codex.count).toBe(1);
    expect(codex.successCount).toBe(1);
    expect(codex.successRate).toBe(1);
  });

  it("defaults missing engine to 'claude-code'", () => {
    const outcomes = [
      makeOutcome({ engine: undefined }),
      makeOutcome({ engine: "" }),
    ];
    const breakdown = computeEngineBreakdown(outcomes);
    // Empty string is falsy, so both should default to "claude-code"
    expect(breakdown).toHaveLength(1);
    expect(breakdown[0].engine).toBe("claude-code");
    expect(breakdown[0].count).toBe(2);
  });

  it("computes average cost per engine", () => {
    const outcomes = [
      makeOutcome({ engine: "claude-code", cost_usd: 0.10 }),
      makeOutcome({ engine: "claude-code", cost_usd: 0.20 }),
    ];
    const breakdown = computeEngineBreakdown(outcomes);
    expect(breakdown[0].avgCost).toBeCloseTo(0.15, 5);
  });

  it("computes average duration per engine", () => {
    const outcomes = [
      makeOutcome({ engine: "claude-code", duration_ms: 100000 }),
      makeOutcome({ engine: "claude-code", duration_ms: 200000 }),
    ];
    const breakdown = computeEngineBreakdown(outcomes);
    expect(breakdown[0].avgDuration).toBe(150000);
  });

  it("returns empty array for no outcomes", () => {
    const breakdown = computeEngineBreakdown([]);
    expect(breakdown).toEqual([]);
  });

  it("handles outcomes without cost or duration", () => {
    const outcomes = [
      makeOutcome({ engine: "claude-code", cost_usd: undefined, duration_ms: undefined }),
    ];
    const breakdown = computeEngineBreakdown(outcomes);
    expect(breakdown[0].avgCost).toBe(0);
    expect(breakdown[0].avgDuration).toBe(0);
  });
});

describe("computeModelBreakdown", () => {
  it("groups outcomes by model", () => {
    const outcomes = [
      makeOutcome({ model: "claude-sonnet-4-6", outcome: "clean" }),
      makeOutcome({ model: "claude-sonnet-4-6", outcome: "tests-failed" }),
      makeOutcome({ model: "claude-opus-4-6", outcome: "clean" }),
    ];
    const breakdown = computeModelBreakdown(outcomes);
    expect(breakdown).toHaveLength(2);

    const sonnet = breakdown.find((b) => b.model === "claude-sonnet-4-6")!;
    expect(sonnet.count).toBe(2);
    expect(sonnet.successCount).toBe(1);
    expect(sonnet.failureCount).toBe(1);
    expect(sonnet.successRate).toBe(0.5);

    const opus = breakdown.find((b) => b.model === "claude-opus-4-6")!;
    expect(opus.count).toBe(1);
    expect(opus.successRate).toBe(1);
  });

  it("defaults missing model to 'unknown'", () => {
    const outcomes = [makeOutcome({ model: undefined })];
    const breakdown = computeModelBreakdown(outcomes);
    expect(breakdown).toHaveLength(1);
    expect(breakdown[0].model).toBe("unknown");
  });

  it("detects write stage when no review_model", () => {
    const outcomes = [
      makeOutcome({ model: "claude-sonnet-4-6", review_model: undefined }),
    ];
    const breakdown = computeModelBreakdown(outcomes);
    expect(breakdown[0].stages).toContain("write");
    expect(breakdown[0].stages).not.toContain("review");
  });

  it("detects write and review stages when review_model is present", () => {
    const outcomes = [
      makeOutcome({ model: "claude-sonnet-4-6", review_model: "claude-opus-4-6" }),
    ];
    const breakdown = computeModelBreakdown(outcomes);
    expect(breakdown[0].stages).toContain("write");
    expect(breakdown[0].stages).toContain("review");
  });

  it("returns empty array for no outcomes", () => {
    const breakdown = computeModelBreakdown([]);
    expect(breakdown).toEqual([]);
  });
});

describe("computeCheckHealth", () => {
  it("computes pass rates for all check types", () => {
    const outcomes = [
      makeOutcome({
        checks: { gate: "success", tests: "success", review: "success", spec_audit: "success" },
      }),
      makeOutcome({
        checks: { gate: "success", tests: "failure", review: "success", spec_audit: "skipped" },
      }),
    ];
    const health = computeCheckHealth(outcomes);
    expect(health).toHaveLength(4);

    const gate = health.find((h) => h.name === "Gate")!;
    expect(gate.passed).toBe(2);
    expect(gate.failed).toBe(0);
    expect(gate.passRate).toBe(1);

    const tests = health.find((h) => h.name === "Tests")!;
    expect(tests.passed).toBe(1);
    expect(tests.failed).toBe(1);
    expect(tests.passRate).toBe(0.5);

    const specAudit = health.find((h) => h.name === "Spec Audit")!;
    expect(specAudit.passed).toBe(1);
    expect(specAudit.skipped).toBe(1);
    // passRate is based on evaluated (passed + failed), not total
    expect(specAudit.passRate).toBe(1);
  });

  it("handles all checks being skipped", () => {
    const outcomes = [
      makeOutcome({
        checks: { gate: "skipped", tests: "skipped", review: "skipped", spec_audit: "skipped" },
      }),
    ];
    const health = computeCheckHealth(outcomes);
    for (const check of health) {
      expect(check.passed).toBe(0);
      expect(check.failed).toBe(0);
      expect(check.skipped).toBe(1);
      expect(check.passRate).toBe(0);
    }
  });

  it("handles all checks failing", () => {
    const outcomes = [
      makeOutcome({
        checks: { gate: "failure", tests: "failure", review: "failure", spec_audit: "failure" },
      }),
      makeOutcome({
        checks: { gate: "failure", tests: "failure", review: "failure", spec_audit: "failure" },
      }),
    ];
    const health = computeCheckHealth(outcomes);
    for (const check of health) {
      expect(check.passed).toBe(0);
      expect(check.failed).toBe(2);
      expect(check.passRate).toBe(0);
    }
  });

  it("returns correct check names including Spec Audit capitalization", () => {
    const health = computeCheckHealth([
      makeOutcome(),
    ]);
    const names = health.map((h) => h.name);
    expect(names).toEqual(["Gate", "Tests", "Review", "Spec Audit"]);
  });

  it("handles empty outcomes array", () => {
    const health = computeCheckHealth([]);
    expect(health).toHaveLength(4);
    for (const check of health) {
      expect(check.passed).toBe(0);
      expect(check.failed).toBe(0);
      expect(check.skipped).toBe(0);
      expect(check.passRate).toBe(0);
    }
  });
});

describe("computeRiskBreakdown", () => {
  it("groups outcomes by risk tier", () => {
    const outcomes = [
      makeOutcome({ risk_tier: "high", outcome: "clean" }),
      makeOutcome({ risk_tier: "high", outcome: "tests-failed" }),
      makeOutcome({ risk_tier: "medium", outcome: "clean" }),
      makeOutcome({ risk_tier: "low", outcome: "clean" }),
    ];
    const breakdown = computeRiskBreakdown(outcomes);
    expect(breakdown).toHaveLength(3);

    const high = breakdown.find((b) => b.tier === "high")!;
    expect(high.count).toBe(2);
    expect(high.successCount).toBe(1);
    expect(high.failureCount).toBe(1);
    expect(high.successRate).toBe(0.5);

    const low = breakdown.find((b) => b.tier === "low")!;
    expect(low.count).toBe(1);
    expect(low.successRate).toBe(1);
  });

  it("filters out empty tiers", () => {
    const outcomes = [
      makeOutcome({ risk_tier: "medium", outcome: "clean" }),
    ];
    const breakdown = computeRiskBreakdown(outcomes);
    expect(breakdown).toHaveLength(1);
    expect(breakdown[0].tier).toBe("medium");
  });

  it("returns empty array when no outcomes", () => {
    const breakdown = computeRiskBreakdown([]);
    expect(breakdown).toEqual([]);
  });

  it("computes success rate within each tier independently", () => {
    const outcomes = [
      makeOutcome({ risk_tier: "high", outcome: "tests-failed" }),
      makeOutcome({ risk_tier: "high", outcome: "tests-failed" }),
      makeOutcome({ risk_tier: "low", outcome: "clean" }),
      makeOutcome({ risk_tier: "low", outcome: "clean" }),
    ];
    const breakdown = computeRiskBreakdown(outcomes);

    const high = breakdown.find((b) => b.tier === "high")!;
    expect(high.successRate).toBe(0);

    const low = breakdown.find((b) => b.tier === "low")!;
    expect(low.successRate).toBe(1);
  });
});

describe("computeFileHotspots", () => {
  it("counts file appearances across outcomes", () => {
    const outcomes = [
      makeOutcome({ files_changed: ["src/main.py", "src/utils.py"] }),
      makeOutcome({ files_changed: ["src/main.py", "tests/test_main.py"] }),
      makeOutcome({ files_changed: ["src/main.py"] }),
    ];
    const hotspots = computeFileHotspots(outcomes);

    const mainPy = hotspots.find((h) => h.path === "src/main.py")!;
    expect(mainPy.appearances).toBe(3);

    const utilsPy = hotspots.find((h) => h.path === "src/utils.py")!;
    expect(utilsPy.appearances).toBe(1);
  });

  it("sorts by frequency descending", () => {
    const outcomes = [
      makeOutcome({ files_changed: ["a.py"] }),
      makeOutcome({ files_changed: ["b.py", "a.py"] }),
      makeOutcome({ files_changed: ["c.py", "b.py", "a.py"] }),
    ];
    const hotspots = computeFileHotspots(outcomes);
    expect(hotspots[0].path).toBe("a.py");
    expect(hotspots[0].appearances).toBe(3);
    expect(hotspots[1].path).toBe("b.py");
    expect(hotspots[1].appearances).toBe(2);
    expect(hotspots[2].path).toBe("c.py");
    expect(hotspots[2].appearances).toBe(1);
  });

  it("tracks success and failure splits", () => {
    const outcomes = [
      makeOutcome({ files_changed: ["src/main.py"], outcome: "clean" }),
      makeOutcome({ files_changed: ["src/main.py"], outcome: "tests-failed" }),
      makeOutcome({ files_changed: ["src/main.py"], outcome: "clean" }),
    ];
    const hotspots = computeFileHotspots(outcomes);
    const mainPy = hotspots.find((h) => h.path === "src/main.py")!;
    expect(mainPy.inSuccessful).toBe(2);
    expect(mainPy.inFailed).toBe(1);
  });

  it("limits results to 20 files", () => {
    const files = Array.from({ length: 25 }, (_, i) => `file-${i}.py`);
    const outcomes = [makeOutcome({ files_changed: files })];
    const hotspots = computeFileHotspots(outcomes);
    expect(hotspots).toHaveLength(20);
  });

  it("returns empty array for outcomes with no files", () => {
    const outcomes = [
      makeOutcome({ files_changed: [] }),
      makeOutcome({ files_changed: [] }),
    ];
    const hotspots = computeFileHotspots(outcomes);
    expect(hotspots).toEqual([]);
  });

  it("returns empty array for no outcomes", () => {
    const hotspots = computeFileHotspots([]);
    expect(hotspots).toEqual([]);
  });
});
