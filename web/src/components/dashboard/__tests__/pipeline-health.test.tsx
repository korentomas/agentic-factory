import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { PipelineHealth } from "../pipeline-health";
import type { CheckHealth, RiskBreakdown } from "@/lib/data/types";

function makeCheck(overrides: Partial<CheckHealth> = {}): CheckHealth {
  return {
    name: "Gate Check",
    passed: 18,
    failed: 2,
    skipped: 0,
    passRate: 0.9,
    ...overrides,
  };
}

function makeRisk(overrides: Partial<RiskBreakdown> = {}): RiskBreakdown {
  return {
    tier: "medium",
    count: 10,
    successCount: 8,
    failureCount: 2,
    successRate: 0.8,
    ...overrides,
  };
}

describe("PipelineHealth", () => {
  it("renders all check pass rate bars", () => {
    const checks = [
      makeCheck({ name: "Gate Check" }),
      makeCheck({ name: "Tests" }),
      makeCheck({ name: "Review" }),
      makeCheck({ name: "Spec Audit" }),
    ];
    render(<PipelineHealth checks={checks} risks={[]} />);

    expect(screen.getByText("Gate Check")).toBeInTheDocument();
    expect(screen.getByText("Tests")).toBeInTheDocument();
    expect(screen.getByText("Review")).toBeInTheDocument();
    expect(screen.getByText("Spec Audit")).toBeInTheDocument();
  });

  it("shows correct percentages for checks", () => {
    const checks = [
      makeCheck({ name: "Gate Check", passRate: 0.95 }),
      makeCheck({ name: "Tests", passRate: 0.6 }),
    ];
    render(<PipelineHealth checks={checks} risks={[]} />);

    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
  });

  it("shows passed/failed/skipped counts", () => {
    const checks = [
      makeCheck({ passed: 18, failed: 2, skipped: 0 }),
    ];
    render(<PipelineHealth checks={checks} risks={[]} />);

    expect(screen.getByText("18 passed")).toBeInTheDocument();
    expect(screen.getByText("2 failed")).toBeInTheDocument();
    // skipped = 0, so it should not be shown
    expect(screen.queryByText(/skipped/)).not.toBeInTheDocument();
  });

  it("shows skipped count when greater than zero", () => {
    const checks = [
      makeCheck({ passed: 15, failed: 3, skipped: 2 }),
    ];
    render(<PipelineHealth checks={checks} risks={[]} />);

    expect(screen.getByText("15 passed")).toBeInTheDocument();
    expect(screen.getByText("3 failed")).toBeInTheDocument();
    expect(screen.getByText("2 skipped")).toBeInTheDocument();
  });

  it("renders risk tier cards", () => {
    const risks = [
      makeRisk({ tier: "high", count: 5, successRate: 0.4 }),
      makeRisk({ tier: "medium", count: 10, successRate: 0.8 }),
      makeRisk({ tier: "low", count: 15, successRate: 0.93 }),
    ];
    render(<PipelineHealth checks={[]} risks={risks} />);

    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
    expect(screen.getByText("low")).toBeInTheDocument();
  });

  it("shows tier task counts", () => {
    const risks = [
      makeRisk({ tier: "high", count: 5 }),
      makeRisk({ tier: "low", count: 15 }),
    ];
    render(<PipelineHealth checks={[]} risks={risks} />);

    expect(screen.getByText("5 tasks")).toBeInTheDocument();
    expect(screen.getByText("15 tasks")).toBeInTheDocument();
  });

  it("shows success rate per tier as percentage", () => {
    const risks = [
      makeRisk({ tier: "high", successRate: 0.4, successCount: 2, count: 5 }),
      makeRisk({ tier: "medium", successRate: 0.8, successCount: 8, count: 10 }),
    ];
    render(<PipelineHealth checks={[]} risks={risks} />);

    expect(screen.getByText("40%")).toBeInTheDocument();
    expect(screen.getByText("80%")).toBeInTheDocument();
  });

  it("shows shipped counts per tier", () => {
    const risks = [
      makeRisk({ tier: "high", successCount: 2, count: 5 }),
      makeRisk({ tier: "low", successCount: 14, count: 15 }),
    ];
    render(<PipelineHealth checks={[]} risks={risks} />);

    expect(screen.getByText("2/5 shipped")).toBeInTheDocument();
    expect(screen.getByText("14/15 shipped")).toBeInTheDocument();
  });

  it("renders section headings", () => {
    render(<PipelineHealth checks={[]} risks={[]} />);

    expect(screen.getByText("Pipeline Checks")).toBeInTheDocument();
    expect(screen.getByText("Risk Tiers")).toBeInTheDocument();
  });

  it("renders section descriptions", () => {
    render(<PipelineHealth checks={[]} risks={[]} />);

    expect(screen.getByText("Pass rates across all runs")).toBeInTheDocument();
    expect(screen.getByText("Success rates by risk classification")).toBeInTheDocument();
  });
});
