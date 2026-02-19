import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { LearningPanel } from "../learning-panel";
import type { LearningStats, LearnedPattern } from "@/lib/data/types";

function makePattern(overrides: Partial<LearnedPattern> = {}): LearnedPattern {
  return {
    kind: "pattern",
    description: "Always add type hints to function signatures",
    evidenceCount: 5,
    confidence: 0.85,
    ...overrides,
  };
}

function makeLearning(overrides: Partial<LearningStats> = {}): LearningStats {
  return {
    totalOutcomes: 12,
    patternsDiscovered: 3,
    antiPatternsDiscovered: 1,
    patterns: [],
    lastExtractionDate: null,
    nextExtractionEligible: true,
    ...overrides,
  };
}

describe("LearningPanel", () => {
  it("shows total outcomes, patterns, and anti-patterns counts", () => {
    render(
      <LearningPanel
        learning={makeLearning({
          totalOutcomes: 12,
          patternsDiscovered: 3,
          antiPatternsDiscovered: 1,
        })}
      />
    );

    expect(screen.getByText("12")).toBeInTheDocument();
    // "3" also appears as a milestone label, so use getAllByText
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
    // "1" also appears as a milestone label, so use getAllByText
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Total outcomes")).toBeInTheDocument();
    expect(screen.getByText("Patterns learned")).toBeInTheDocument();
    expect(screen.getByText("Anti-patterns")).toBeInTheDocument();
  });

  it('shows "Extraction ready" when eligible', () => {
    render(
      <LearningPanel
        learning={makeLearning({ nextExtractionEligible: true })}
      />
    );

    expect(screen.getByText("Extraction ready")).toBeInTheDocument();
  });

  it('shows "Need N more outcomes" when not eligible', () => {
    render(
      <LearningPanel
        learning={makeLearning({
          nextExtractionEligible: false,
          totalOutcomes: 1,
        })}
      />
    );

    expect(screen.getByText("Need 2 more outcomes")).toBeInTheDocument();
  });

  it("shows need 3 more outcomes when zero outcomes", () => {
    render(
      <LearningPanel
        learning={makeLearning({
          nextExtractionEligible: false,
          totalOutcomes: 0,
        })}
      />
    );

    expect(screen.getByText("Need 3 more outcomes")).toBeInTheDocument();
  });

  it("renders milestone dots with numbers", () => {
    render(<LearningPanel learning={makeLearning({ totalOutcomes: 5 })} />);

    // All milestone numbers should be present: 1, 2, 3, 5, 10, 20, 50
    // Some numbers overlap with stats (1 = antiPatternsDiscovered, 3 = patternsDiscovered, 5 = totalOutcomes)
    // so we use getAllByText for those
    expect(screen.getAllByText("1").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getAllByText("3").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("5").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("20")).toBeInTheDocument();
    expect(screen.getByText("50")).toBeInTheDocument();
  });

  it("renders discovered patterns with descriptions", () => {
    const patterns = [
      makePattern({
        kind: "pattern",
        description: "Always add type hints to function signatures",
      }),
      makePattern({
        kind: "anti-pattern",
        description: "Never use bare except clauses",
      }),
    ];
    render(
      <LearningPanel learning={makeLearning({ patterns })} />
    );

    expect(screen.getByText("Always add type hints to function signatures")).toBeInTheDocument();
    expect(screen.getByText("Never use bare except clauses")).toBeInTheDocument();
    expect(screen.getByText("Active Rules")).toBeInTheDocument();
  });

  it("shows empty state when no patterns", () => {
    render(
      <LearningPanel learning={makeLearning({ patterns: [] })} />
    );

    expect(
      screen.getByText(/No patterns extracted yet/)
    ).toBeInTheDocument();
  });

  it("shows confidence and evidence count", () => {
    const patterns = [
      makePattern({ evidenceCount: 5, confidence: 0.85 }),
    ];
    render(
      <LearningPanel learning={makeLearning({ patterns })} />
    );

    expect(screen.getByText("Evidence: 5 runs")).toBeInTheDocument();
    expect(screen.getByText("Confidence: 85%")).toBeInTheDocument();
  });

  it("shows pattern kind badge", () => {
    const patterns = [
      makePattern({ kind: "pattern" }),
      makePattern({
        kind: "anti-pattern",
        description: "Avoid hardcoded values",
      }),
    ];
    render(
      <LearningPanel learning={makeLearning({ patterns })} />
    );

    expect(screen.getByText("pattern")).toBeInTheDocument();
    expect(screen.getByText("anti-pattern")).toBeInTheDocument();
  });

  it("shows last extraction date when available", () => {
    render(
      <LearningPanel
        learning={makeLearning({
          lastExtractionDate: "2025-03-15T10:00:00Z",
        })}
      />
    );

    expect(screen.getByText(/Last extraction:/)).toBeInTheDocument();
    expect(screen.getByText(/Mar 15, 2025/)).toBeInTheDocument();
  });

  it("does not show last extraction date when null", () => {
    render(
      <LearningPanel
        learning={makeLearning({ lastExtractionDate: null })}
      />
    );

    expect(screen.queryByText(/Last extraction/)).not.toBeInTheDocument();
  });

  it("renders the section heading and description", () => {
    render(<LearningPanel learning={makeLearning()} />);

    expect(screen.getByText("Self-Learning Pipeline")).toBeInTheDocument();
    expect(screen.getByText("Patterns extracted from agent outcomes")).toBeInTheDocument();
  });
});
