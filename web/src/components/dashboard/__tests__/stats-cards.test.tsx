import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatsCards } from "../stats-cards";
import type { DashboardStats } from "@/lib/data/types";

function makeStats(overrides: Partial<DashboardStats> = {}): DashboardStats {
  return {
    totalTasks: 42,
    tasksThisMonth: 8,
    prsShipped: 35,
    prsClean: 30,
    prsFailed: 5,
    successRate: 0.85,
    totalCost: 12.5,
    costThisMonth: 3.2,
    avgDurationMs: 180000,
    ...overrides,
  };
}

describe("StatsCards", () => {
  it("renders all 4 stat cards with correct labels", () => {
    render(<StatsCards stats={makeStats()} />);

    expect(screen.getByText("Tasks this month")).toBeInTheDocument();
    expect(screen.getByText("PRs shipped")).toBeInTheDocument();
    expect(screen.getByText("Success rate")).toBeInTheDocument();
    expect(screen.getByText("Avg duration")).toBeInTheDocument();
  });

  it("shows correct task values", () => {
    render(<StatsCards stats={makeStats({ tasksThisMonth: 8, totalTasks: 42 })} />);

    expect(screen.getByText("8")).toBeInTheDocument();
    expect(screen.getByText("42 all time")).toBeInTheDocument();
  });

  it("shows correct PR values", () => {
    render(<StatsCards stats={makeStats({ prsClean: 30, prsFailed: 5 })} />);

    expect(screen.getByText("30")).toBeInTheDocument();
    expect(screen.getByText("5 failed")).toBeInTheDocument();
  });

  it("shows correct success rate as percentage", () => {
    render(<StatsCards stats={makeStats({ successRate: 0.85 })} />);

    expect(screen.getByText("85%")).toBeInTheDocument();
  });

  it('shows "--" when success rate is zero', () => {
    render(<StatsCards stats={makeStats({ successRate: 0 })} />);

    // The success rate value and avg duration value can both show "--"
    // Success rate zero => "--", and we check the "Critical" sub-label
    const dashes = screen.getAllByText("--");
    expect(dashes.length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it('shows "Healthy" when success rate >= 0.8', () => {
    render(<StatsCards stats={makeStats({ successRate: 0.8 })} />);

    expect(screen.getByText("Healthy")).toBeInTheDocument();
  });

  it('shows "Needs attention" when success rate >= 0.5 and < 0.8', () => {
    render(<StatsCards stats={makeStats({ successRate: 0.6 })} />);

    expect(screen.getByText("Needs attention")).toBeInTheDocument();
  });

  it('shows "Critical" when success rate < 0.5', () => {
    render(<StatsCards stats={makeStats({ successRate: 0.3 })} />);

    expect(screen.getByText("Critical")).toBeInTheDocument();
  });

  it("formats avg duration from ms to minutes", () => {
    render(<StatsCards stats={makeStats({ avgDurationMs: 180000 })} />);

    expect(screen.getByText("3m")).toBeInTheDocument();
  });

  it("formats avg duration as seconds when under 60s", () => {
    render(<StatsCards stats={makeStats({ avgDurationMs: 45000 })} />);

    expect(screen.getByText("45s")).toBeInTheDocument();
  });

  it('shows "--" for zero avg duration', () => {
    render(<StatsCards stats={makeStats({ avgDurationMs: 0, successRate: 0.9 })} />);

    expect(screen.getByText("--")).toBeInTheDocument();
  });

  it("formats total cost correctly", () => {
    render(<StatsCards stats={makeStats({ totalCost: 12.5 })} />);

    expect(screen.getByText("$12.50 total cost")).toBeInTheDocument();
  });

  it("shows $0 for zero total cost", () => {
    render(<StatsCards stats={makeStats({ totalCost: 0 })} />);

    expect(screen.getByText("$0 total cost")).toBeInTheDocument();
  });

  it("shows <$0.01 for very small costs", () => {
    render(<StatsCards stats={makeStats({ totalCost: 0.005 })} />);

    expect(screen.getByText("<$0.01 total cost")).toBeInTheDocument();
  });
});
