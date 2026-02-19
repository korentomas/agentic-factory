import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TasksSidebar } from "../tasks-sidebar";

function makePlan(
  overrides: Partial<{
    revision: number;
    steps: Array<{
      title: string;
      description: string;
      status: "pending" | "in_progress" | "completed" | "skipped";
    }>;
    createdBy: string;
    createdAt: Date;
  }> = {},
) {
  return {
    revision: 1,
    steps: [
      {
        title: "Read codebase",
        description: "Understand the existing code",
        status: "completed" as const,
      },
      {
        title: "Write implementation",
        description: "Code the solution",
        status: "in_progress" as const,
      },
      {
        title: "Write tests",
        description: "Add unit tests",
        status: "pending" as const,
      },
    ],
    createdBy: "claude-code",
    createdAt: new Date("2026-02-19T12:00:00Z"),
    ...overrides,
  };
}

describe("TasksSidebar", () => {
  it("not visible when open=false (translate-x-full)", () => {
    const { container } = render(
      <TasksSidebar open={false} onClose={vi.fn()} plans={[makePlan()]} />,
    );

    // The panel div should have translate-x-full class
    const panel = container.querySelector(".translate-x-full");
    expect(panel).toBeInTheDocument();
  });

  it("visible when open=true (translate-x-0)", () => {
    const { container } = render(
      <TasksSidebar open={true} onClose={vi.fn()} plans={[makePlan()]} />,
    );

    const panel = container.querySelector(".translate-x-0");
    expect(panel).toBeInTheDocument();
  });

  it("shows plan steps", () => {
    render(
      <TasksSidebar open={true} onClose={vi.fn()} plans={[makePlan()]} />,
    );

    expect(screen.getByText("Read codebase")).toBeInTheDocument();
    expect(screen.getByText("Write implementation")).toBeInTheDocument();
    expect(screen.getByText("Write tests")).toBeInTheDocument();
  });

  it("shows completed steps with check icon", () => {
    const plan = makePlan({
      steps: [
        {
          title: "Done step",
          description: "Already finished",
          status: "completed",
        },
      ],
    });
    const { container } = render(
      <TasksSidebar open={true} onClose={vi.fn()} plans={[plan]} />,
    );

    expect(screen.getByText("Done step")).toBeInTheDocument();
    // CheckCircle2 from lucide renders an svg with the success color
    const successIcons = container.querySelectorAll(
      ".text-\\[var\\(--color-success\\)\\]",
    );
    expect(successIcons.length).toBeGreaterThan(0);
  });

  it("calls onClose when X button clicked", async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(
      <TasksSidebar open={true} onClose={onClose} plans={[makePlan()]} />,
    );

    const closeButton = screen.getByRole("button", {
      name: /close sidebar/i,
    });
    await user.click(closeButton);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows revision navigation when multiple plans exist", () => {
    const plans = [
      makePlan({ revision: 1 }),
      makePlan({ revision: 2 }),
    ];
    render(
      <TasksSidebar open={true} onClose={vi.fn()} plans={plans} />,
    );

    expect(screen.getByText("Revision 1 of 2")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /previous revision/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /next revision/i }),
    ).toBeInTheDocument();
  });

  it("filter buttons work (All, Completed, Current, Pending)", async () => {
    const user = userEvent.setup();
    render(
      <TasksSidebar open={true} onClose={vi.fn()} plans={[makePlan()]} />,
    );

    // All filter — all 3 steps visible
    expect(screen.getByText("Read codebase")).toBeInTheDocument();
    expect(screen.getByText("Write implementation")).toBeInTheDocument();
    expect(screen.getByText("Write tests")).toBeInTheDocument();

    // Click "Completed" filter
    await user.click(screen.getByText("Completed"));
    expect(screen.getByText("Read codebase")).toBeInTheDocument();
    expect(screen.queryByText("Write implementation")).not.toBeInTheDocument();
    expect(screen.queryByText("Write tests")).not.toBeInTheDocument();

    // Click "Current" filter
    await user.click(screen.getByText("Current"));
    expect(screen.queryByText("Read codebase")).not.toBeInTheDocument();
    expect(screen.getByText("Write implementation")).toBeInTheDocument();
    expect(screen.queryByText("Write tests")).not.toBeInTheDocument();

    // Click "Pending" filter
    await user.click(screen.getByText("Pending"));
    expect(screen.queryByText("Read codebase")).not.toBeInTheDocument();
    expect(screen.queryByText("Write implementation")).not.toBeInTheDocument();
    expect(screen.getByText("Write tests")).toBeInTheDocument();

    // Click "All" to restore
    await user.click(screen.getByText("All"));
    expect(screen.getByText("Read codebase")).toBeInTheDocument();
    expect(screen.getByText("Write implementation")).toBeInTheDocument();
    expect(screen.getByText("Write tests")).toBeInTheDocument();
  });
});
