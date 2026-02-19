import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PRTable } from "../pr-table";
import type { PRDetail, OutcomeChecks } from "@/lib/data/types";

function makeChecks(overrides: Partial<OutcomeChecks> = {}): OutcomeChecks {
  return {
    gate: "success",
    tests: "success",
    review: "success",
    spec_audit: "success",
    ...overrides,
  };
}

function makePR(overrides: Partial<PRDetail> = {}): PRDetail {
  return {
    number: 101,
    url: "https://github.com/test-org/test-repo/pull/101",
    title: "feat: add user authentication",
    state: "merged",
    branch: "feat/auth",
    outcome: "clean",
    riskTier: "medium",
    engine: "claude-code",
    model: "claude-sonnet-4-6",
    cost: 0.15,
    duration: 120000,
    numTurns: 5,
    filesChanged: ["src/auth.ts", "src/middleware.ts"],
    checksStatus: makeChecks(),
    timestamp: new Date().toISOString(),
    mergedAt: new Date().toISOString(),
    ...overrides,
  };
}

describe("PRTable", () => {
  it("renders empty state message when no PRs", () => {
    render(<PRTable prs={[]} />);

    expect(screen.getByText(/No PRs yet/)).toBeInTheDocument();
    expect(screen.getByText("ai-agent")).toBeInTheDocument();
  });

  it("renders PR rows with correct data", () => {
    const pr = makePR({
      number: 42,
      title: "fix: resolve login bug",
      engine: "aider",
    });
    render(<PRTable prs={[pr]} />);

    expect(screen.getByText("#42")).toBeInTheDocument();
    expect(screen.getByText("fix: resolve login bug")).toBeInTheDocument();
    expect(screen.getByText("aider")).toBeInTheDocument();
  });

  it("shows Shipped badge for clean outcome", () => {
    render(<PRTable prs={[makePR({ outcome: "clean" })]} />);

    expect(screen.getByText("Shipped")).toBeInTheDocument();
  });

  it("shows Review Failed badge", () => {
    render(<PRTable prs={[makePR({ outcome: "review-failed" })]} />);

    expect(screen.getByText("Review Failed")).toBeInTheDocument();
  });

  it("shows Tests Failed badge", () => {
    render(<PRTable prs={[makePR({ outcome: "tests-failed" })]} />);

    expect(screen.getByText("Tests Failed")).toBeInTheDocument();
  });

  it("shows Blocked badge", () => {
    render(<PRTable prs={[makePR({ outcome: "blocked" })]} />);

    expect(screen.getByText("Blocked")).toBeInTheDocument();
  });

  it("shows risk badges with correct text", () => {
    render(
      <PRTable
        prs={[
          makePR({ number: 1, riskTier: "high" }),
          makePR({ number: 2, riskTier: "medium" }),
          makePR({ number: 3, riskTier: "low" }),
        ]}
      />
    );

    expect(screen.getByText("high")).toBeInTheDocument();
    expect(screen.getByText("medium")).toBeInTheDocument();
    expect(screen.getByText("low")).toBeInTheDocument();
  });

  it("click expands row to show details", async () => {
    const user = userEvent.setup();
    const pr = makePR({
      model: "claude-sonnet-4-6",
      cost: 0.25,
      duration: 90000,
      numTurns: 7,
      filesChanged: ["src/index.ts"],
    });
    render(<PRTable prs={[pr]} />);

    // Details should not be visible initially
    expect(screen.queryByText("Model")).not.toBeInTheDocument();

    // Click the row to expand
    const row = screen.getByText("feat: add user authentication").closest("tr")!;
    await user.click(row);

    // Details should now be visible
    expect(screen.getByText("Model")).toBeInTheDocument();
    expect(screen.getByText("claude-sonnet-4-6")).toBeInTheDocument();
    expect(screen.getByText("$0.25")).toBeInTheDocument();
    expect(screen.getByText("90s")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText("Files changed")).toBeInTheDocument();
    expect(screen.getByText("src/index.ts")).toBeInTheDocument();
  });

  it("click again collapses the expanded row", async () => {
    const user = userEvent.setup();
    render(<PRTable prs={[makePR()]} />);

    const row = screen.getByText("feat: add user authentication").closest("tr")!;

    // Expand
    await user.click(row);
    expect(screen.getByText("Model")).toBeInTheDocument();

    // Collapse
    await user.click(row);
    expect(screen.queryByText("Model")).not.toBeInTheDocument();
  });

  it("PR number links to GitHub URL", () => {
    const pr = makePR({
      number: 55,
      url: "https://github.com/test-org/test-repo/pull/55",
    });
    render(<PRTable prs={[pr]} />);

    const link = screen.getByText("#55").closest("a")!;
    expect(link).toHaveAttribute(
      "href",
      "https://github.com/test-org/test-repo/pull/55"
    );
    expect(link).toHaveAttribute("target", "_blank");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("check dots render with correct titles for success/failure/skipped", () => {
    const pr = makePR({
      checksStatus: makeChecks({
        gate: "success",
        tests: "failure",
        review: "skipped",
        spec_audit: "success",
      }),
    });
    render(<PRTable prs={[pr]} />);

    const dots = screen.getAllByTitle("success");
    expect(dots.length).toBe(2);

    expect(screen.getByTitle("failure")).toBeInTheDocument();
    expect(screen.getByTitle("skipped")).toBeInTheDocument();
  });

  it("shows file count in the table row", () => {
    const pr = makePR({
      filesChanged: ["a.ts", "b.ts", "c.ts"],
    });
    render(<PRTable prs={[pr]} />);

    expect(screen.getByText("3")).toBeInTheDocument();
  });

  it("shows timeAgo format for recent timestamps", () => {
    // 30 minutes ago
    const thirtyMinAgo = new Date(Date.now() - 30 * 60 * 1000).toISOString();
    render(<PRTable prs={[makePR({ timestamp: thirtyMinAgo })]} />);

    expect(screen.getByText("30m ago")).toBeInTheDocument();
  });

  it("shows timeAgo in hours for older timestamps", () => {
    // 5 hours ago
    const fiveHoursAgo = new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString();
    render(<PRTable prs={[makePR({ timestamp: fiveHoursAgo })]} />);

    expect(screen.getByText("5h ago")).toBeInTheDocument();
  });

  it("shows timeAgo in days for multi-day timestamps", () => {
    // 3 days ago
    const threeDaysAgo = new Date(Date.now() - 3 * 24 * 60 * 60 * 1000).toISOString();
    render(<PRTable prs={[makePR({ timestamp: threeDaysAgo })]} />);

    expect(screen.getByText("3d ago")).toBeInTheDocument();
  });

  it("shows N/A for zero cost in expanded details", async () => {
    const user = userEvent.setup();
    const pr = makePR({ cost: 0, duration: 0, numTurns: 0 });
    render(<PRTable prs={[pr]} />);

    const row = screen.getByText("feat: add user authentication").closest("tr")!;
    await user.click(row);

    const naElements = screen.getAllByText("N/A");
    expect(naElements.length).toBe(3); // cost, duration, turns
  });

  it("renders multiple PR rows", () => {
    const prs = [
      makePR({ number: 10, title: "feat: first PR" }),
      makePR({ number: 20, title: "fix: second PR" }),
      makePR({ number: 30, title: "test: third PR" }),
    ];
    render(<PRTable prs={prs} />);

    expect(screen.getByText("#10")).toBeInTheDocument();
    expect(screen.getByText("#20")).toBeInTheDocument();
    expect(screen.getByText("#30")).toBeInTheDocument();
    expect(screen.getByText("feat: first PR")).toBeInTheDocument();
    expect(screen.getByText("fix: second PR")).toBeInTheDocument();
    expect(screen.getByText("test: third PR")).toBeInTheDocument();
  });
});
