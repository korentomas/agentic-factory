import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TaskProgressBar } from "../task-progress-bar";

function makeSteps(
  statuses: Array<"pending" | "in_progress" | "completed" | "skipped">,
) {
  return statuses.map((status, i) => ({
    title: `Step ${i + 1}`,
    description: `Description for step ${i + 1}`,
    status,
  }));
}

describe("TaskProgressBar", () => {
  it("renders nothing meaningful when steps array is empty", () => {
    render(<TaskProgressBar steps={[]} />);

    // The "0" count is inside a <span>, so use a function matcher
    expect(
      screen.getByText((_, el) => el?.textContent === "0 of 0 steps completed"),
    ).toBeInTheDocument();
    expect(
      screen.getByText((_, el) => el?.tagName === "P" && el?.textContent === "0%"),
    ).toBeInTheDocument();
  });

  it("shows correct completion count and percentage", () => {
    const steps = makeSteps(["completed", "completed", "in_progress", "pending"]);
    render(<TaskProgressBar steps={steps} />);

    expect(
      screen.getByText((_, el) => el?.textContent === "2 of 4 steps completed"),
    ).toBeInTheDocument();
    expect(
      screen.getByText((_, el) => el?.tagName === "P" && el?.textContent === "50%"),
    ).toBeInTheDocument();
  });

  it("renders one segment per step", () => {
    const steps = makeSteps(["completed", "pending", "pending"]);
    const { container } = render(<TaskProgressBar steps={steps} />);

    const buttons = container.querySelectorAll("button");
    expect(buttons).toHaveLength(3);
  });

  it("completed steps have success color", () => {
    const steps = makeSteps(["completed"]);
    const { container } = render(<TaskProgressBar steps={steps} />);

    const segment = container.querySelector("button");
    expect(segment?.className).toContain("bg-[var(--color-success)]"); // extended palette color, not a legacy token
  });

  it("calls onStepClick with correct index when clicked", async () => {
    const user = userEvent.setup();
    const onStepClick = vi.fn();
    const steps = makeSteps(["completed", "in_progress", "pending"]);
    render(<TaskProgressBar steps={steps} onStepClick={onStepClick} />);

    const buttons = screen.getAllByRole("button");
    await user.click(buttons[1]);

    expect(onStepClick).toHaveBeenCalledWith(1);
  });
});
