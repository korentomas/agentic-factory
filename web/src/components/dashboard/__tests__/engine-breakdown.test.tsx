import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { EngineBreakdownPanel } from "../engine-breakdown";
import type { EngineBreakdown, ModelBreakdown } from "@/lib/data/types";

function makeEngine(overrides: Partial<EngineBreakdown> = {}): EngineBreakdown {
  return {
    engine: "claude-code",
    count: 20,
    successCount: 16,
    failureCount: 4,
    successRate: 0.8,
    avgCost: 0.18,
    avgDuration: 95000,
    ...overrides,
  };
}

function makeModel(overrides: Partial<ModelBreakdown> = {}): ModelBreakdown {
  return {
    model: "claude-sonnet-4-6",
    count: 15,
    successCount: 12,
    failureCount: 3,
    successRate: 0.8,
    stages: ["write", "review"],
    ...overrides,
  };
}

describe("EngineBreakdownPanel", () => {
  it("renders engine section with engine names", () => {
    render(
      <EngineBreakdownPanel
        engines={[
          makeEngine({ engine: "claude-code" }),
          makeEngine({ engine: "aider" }),
        ]}
        models={[]}
      />
    );

    expect(screen.getByText("Engines")).toBeInTheDocument();
    expect(screen.getByText("claude-code")).toBeInTheDocument();
    expect(screen.getByText("aider")).toBeInTheDocument();
  });

  it("shows task counts and success rates for engines", () => {
    render(
      <EngineBreakdownPanel
        engines={[makeEngine({ count: 20, successRate: 0.8 })]}
        models={[]}
      />
    );

    // The component renders "20 tasks · 80% success" as one text node with middot
    expect(screen.getByText(/20 tasks/)).toBeInTheDocument();
    expect(screen.getByText(/80% success/)).toBeInTheDocument();
  });

  it("renders model section with model names", () => {
    render(
      <EngineBreakdownPanel
        engines={[]}
        models={[
          makeModel({ model: "claude-sonnet-4-6" }),
          makeModel({ model: "claude-opus-4-6" }),
        ]}
      />
    );

    expect(screen.getByText("Models")).toBeInTheDocument();
    expect(screen.getByText("claude-sonnet-4-6")).toBeInTheDocument();
    expect(screen.getByText("claude-opus-4-6")).toBeInTheDocument();
  });

  it("shows task counts and success rates for models", () => {
    render(
      <EngineBreakdownPanel
        engines={[]}
        models={[makeModel({ count: 15, successRate: 0.8 })]}
      />
    );

    expect(screen.getByText(/15 tasks/)).toBeInTheDocument();
    expect(screen.getByText(/80% success/)).toBeInTheDocument();
  });

  it('shows "No engine data yet" when engines array is empty', () => {
    render(<EngineBreakdownPanel engines={[]} models={[makeModel()]} />);

    expect(screen.getByText("No engine data yet")).toBeInTheDocument();
  });

  it('shows "No model data yet" when models array is empty', () => {
    render(<EngineBreakdownPanel engines={[makeEngine()]} models={[]} />);

    expect(screen.getByText("No model data yet")).toBeInTheDocument();
  });

  it("shows both empty messages when both are empty", () => {
    render(<EngineBreakdownPanel engines={[]} models={[]} />);

    expect(screen.getByText("No engine data yet")).toBeInTheDocument();
    expect(screen.getByText("No model data yet")).toBeInTheDocument();
  });

  it("shows avg cost and duration for engines", () => {
    render(
      <EngineBreakdownPanel
        engines={[makeEngine({ avgCost: 0.18, avgDuration: 95000 })]}
        models={[]}
      />
    );

    expect(screen.getByText(/Avg cost: \$0\.18/)).toBeInTheDocument();
    expect(screen.getByText(/Avg duration: 95s/)).toBeInTheDocument();
  });

  it("does not show avg cost when zero", () => {
    render(
      <EngineBreakdownPanel
        engines={[makeEngine({ avgCost: 0 })]}
        models={[]}
      />
    );

    expect(screen.queryByText(/Avg cost/)).not.toBeInTheDocument();
  });

  it("renders model stage badges", () => {
    render(
      <EngineBreakdownPanel
        engines={[]}
        models={[makeModel({ stages: ["write", "review", "triage"] })]}
      />
    );

    expect(screen.getByText("write")).toBeInTheDocument();
    expect(screen.getByText("review")).toBeInTheDocument();
    expect(screen.getByText("triage")).toBeInTheDocument();
  });

  it("renders section descriptions", () => {
    render(<EngineBreakdownPanel engines={[]} models={[]} />);

    expect(screen.getByText("Tasks by coding engine")).toBeInTheDocument();
    expect(screen.getByText("Tasks by AI model")).toBeInTheDocument();
  });
});
