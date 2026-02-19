import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ThreadCard } from "../thread-card";

vi.mock("next/link", () => ({
  default: ({
    href,
    children,
    ...props
  }: {
    href: string;
    children: React.ReactNode;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

function makeThread(overrides: Partial<Parameters<typeof ThreadCard>[0]["thread"]> = {}) {
  return {
    id: "task-42",
    title: "Fix auth flow",
    branch: "fix/auth-flow",
    status: "pending",
    engine: null,
    costUsd: 0,
    durationMs: 0,
    createdAt: new Date(),
    ...overrides,
  };
}

describe("ThreadCard", () => {
  it("renders thread title", () => {
    render(<ThreadCard thread={makeThread({ title: "Add dark mode" })} />);

    expect(screen.getByText("Add dark mode")).toBeInTheDocument();
  });

  it("shows branch name", () => {
    render(<ThreadCard thread={makeThread({ branch: "feat/dark-mode" })} />);

    expect(screen.getByText("feat/dark-mode")).toBeInTheDocument();
  });

  it("shows engine badge when engine is provided", () => {
    render(<ThreadCard thread={makeThread({ engine: "claude-code" })} />);

    expect(screen.getByText("claude-code")).toBeInTheDocument();
  });

  it('displays "Complete" status for complete threads', () => {
    render(<ThreadCard thread={makeThread({ status: "complete" })} />);

    expect(screen.getByText("Complete")).toBeInTheDocument();
  });

  it('displays "Running" status with spinning icon', () => {
    const { container } = render(
      <ThreadCard thread={makeThread({ status: "running" })} />,
    );

    expect(screen.getByText("Running")).toBeInTheDocument();
    const spinner = container.querySelector(".animate-spin");
    expect(spinner).toBeInTheDocument();
  });

  it('displays "Failed" status', () => {
    render(<ThreadCard thread={makeThread({ status: "failed" })} />);

    expect(screen.getByText("Failed")).toBeInTheDocument();
  });

  it("links to /dashboard/tasks/{id}", () => {
    render(<ThreadCard thread={makeThread({ id: "task-99" })} />);

    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/dashboard/tasks/task-99");
  });

  it("shows cost when > 0", () => {
    render(<ThreadCard thread={makeThread({ costUsd: 1.23 })} />);

    expect(screen.getByText("$1.23")).toBeInTheDocument();
  });

  it("shows duration when > 0", () => {
    render(<ThreadCard thread={makeThread({ durationMs: 120000 })} />);

    expect(screen.getByText("2m")).toBeInTheDocument();
  });
});
