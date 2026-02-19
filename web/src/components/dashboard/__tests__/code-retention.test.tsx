import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { CodeRetentionPanel } from "../code-retention";
import type { CodeRetention } from "@/lib/data/types";

function makeRetention(overrides: Partial<CodeRetention> = {}): CodeRetention {
  return {
    prNumber: 42,
    prUrl: "https://github.com/test-org/test-repo/pull/42",
    filesChanged: ["src/auth.ts", "src/middleware.ts"],
    linesWritten: 200,
    linesRetained: 160,
    linesOverwritten: 40,
    overwrittenByAgent: 15,
    overwrittenByHuman: 25,
    retentionRate: 0.8,
    ...overrides,
  };
}

describe("CodeRetentionPanel", () => {
  it("shows empty state when no retention data", () => {
    render(<CodeRetentionPanel retention={[]} />);

    expect(screen.getByText("Code Retention")).toBeInTheDocument();
    expect(
      screen.getByText(/Retention data appears after PRs are merged/)
    ).toBeInTheDocument();
  });

  it("shows retention gauge with correct percentage", () => {
    const retention = [
      makeRetention({ linesWritten: 200, linesRetained: 160 }),
    ];
    render(<CodeRetentionPanel retention={retention} />);

    // overall retention = 160/200 = 80%
    expect(screen.getByText("80%")).toBeInTheDocument();
  });

  it("shows lines written count", () => {
    const retention = [makeRetention({ linesWritten: 1500 })];
    render(<CodeRetentionPanel retention={retention} />);

    expect(screen.getByText("Lines written by agent")).toBeInTheDocument();
    expect(screen.getByText("1,500")).toBeInTheDocument();
  });

  it("shows lines retained count", () => {
    const retention = [makeRetention({ linesRetained: 1200 })];
    render(<CodeRetentionPanel retention={retention} />);

    expect(screen.getByText("Still in codebase")).toBeInTheDocument();
    expect(screen.getByText("1,200")).toBeInTheDocument();
  });

  it("shows overwritten by agent count", () => {
    const retention = [makeRetention({ overwrittenByAgent: 150 })];
    render(<CodeRetentionPanel retention={retention} />);

    expect(screen.getByText("Overwritten by agent")).toBeInTheDocument();
    expect(screen.getByText("150")).toBeInTheDocument();
  });

  it("shows overwritten by human count", () => {
    const retention = [makeRetention({ overwrittenByHuman: 100 })];
    render(<CodeRetentionPanel retention={retention} />);

    expect(screen.getByText("Overwritten by human")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
  });

  it("aggregates stats across multiple PRs", () => {
    const retention = [
      makeRetention({
        prNumber: 1,
        linesWritten: 200,
        linesRetained: 160,
        overwrittenByAgent: 15,
        overwrittenByHuman: 25,
      }),
      makeRetention({
        prNumber: 2,
        linesWritten: 300,
        linesRetained: 240,
        overwrittenByAgent: 30,
        overwrittenByHuman: 30,
      }),
    ];
    render(<CodeRetentionPanel retention={retention} />);

    // totalWritten = 500, totalRetained = 400 => 80%
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("500")).toBeInTheDocument();
    expect(screen.getByText("400")).toBeInTheDocument();
    expect(screen.getByText("45")).toBeInTheDocument(); // 15+30
    expect(screen.getByText("55")).toBeInTheDocument(); // 25+30
  });

  it("shows per-PR breakdown with PR links", () => {
    const retention = [
      makeRetention({
        prNumber: 42,
        prUrl: "https://github.com/test-org/test-repo/pull/42",
        retentionRate: 0.8,
      }),
    ];
    render(<CodeRetentionPanel retention={retention} />);

    expect(screen.getByText("Per-PR Breakdown")).toBeInTheDocument();
    const link = screen.getByText("PR #42");
    expect(link.closest("a")).toHaveAttribute(
      "href",
      "https://github.com/test-org/test-repo/pull/42"
    );
    expect(screen.getByText("80% retained")).toBeInTheDocument();
  });

  it("shows per-PR lines and file counts", () => {
    const retention = [
      makeRetention({
        linesWritten: 200,
        filesChanged: ["a.ts", "b.ts", "c.ts"],
      }),
    ];
    render(<CodeRetentionPanel retention={retention} />);

    expect(screen.getByText("200 lines")).toBeInTheDocument();
    expect(screen.getByText("3 files")).toBeInTheDocument();
  });

  it("shows legend items", () => {
    const retention = [makeRetention()];
    render(<CodeRetentionPanel retention={retention} />);

    expect(screen.getByText("Retained")).toBeInTheDocument();
    expect(screen.getByText("Agent overwrite")).toBeInTheDocument();
    expect(screen.getByText("Human overwrite")).toBeInTheDocument();
  });

  it("renders the heading and description in both empty and data states", () => {
    const { unmount } = render(<CodeRetentionPanel retention={[]} />);
    expect(screen.getByText("Code Retention")).toBeInTheDocument();
    expect(
      screen.getByText("How much agent-written code survives in the codebase")
    ).toBeInTheDocument();
    unmount();

    render(<CodeRetentionPanel retention={[makeRetention()]} />);
    expect(screen.getByText("Code Retention")).toBeInTheDocument();
    expect(
      screen.getByText("How much agent-written code survives in the codebase")
    ).toBeInTheDocument();
  });
});
