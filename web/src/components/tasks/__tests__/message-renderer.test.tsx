import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MessageRenderer } from "../message-renderer";

const NOW = new Date("2026-02-19T14:30:00Z");

describe("MessageRenderer", () => {
  it("renders human message content (right-aligned)", () => {
    const { container } = render(
      <MessageRenderer
        role="human"
        content="Hello from user"
        createdAt={NOW}
      />,
    );

    expect(screen.getByText("Hello from user")).toBeInTheDocument();
    // flex-row-reverse indicates right-alignment
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("flex-row-reverse");
  });

  it("renders assistant message content (left-aligned)", () => {
    const { container } = render(
      <MessageRenderer
        role="assistant"
        content="I found the issue."
        createdAt={NOW}
      />,
    );

    expect(screen.getByText("I found the issue.")).toBeInTheDocument();
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("flex-row");
    expect(wrapper.className).not.toContain("flex-row-reverse");
  });

  it("renders tool call with tool name", async () => {
    const user = userEvent.setup();
    render(
      <MessageRenderer
        role="tool"
        content={null}
        toolName="read_file"
        createdAt={NOW}
      />,
    );

    // Tool name appears in the collapsible button
    expect(screen.getByText("read_file")).toBeInTheDocument();
  });

  it("shows tool input when present", async () => {
    const user = userEvent.setup();
    render(
      <MessageRenderer
        role="tool"
        content={null}
        toolName="write_file"
        toolInput='{"path": "/src/main.py"}'
        createdAt={NOW}
      />,
    );

    // Expand the tool call
    const expandButton = screen.getByText("write_file");
    await user.click(expandButton);

    expect(screen.getByText("Input")).toBeInTheDocument();
    expect(
      screen.getByText('{"path": "/src/main.py"}'),
    ).toBeInTheDocument();
  });

  it("shows tool output when present", async () => {
    const user = userEvent.setup();
    render(
      <MessageRenderer
        role="tool"
        content={null}
        toolName="run_tests"
        toolOutput="All 5 tests passed"
        createdAt={NOW}
      />,
    );

    // Expand the tool call
    const expandButton = screen.getByText("run_tests");
    await user.click(expandButton);

    expect(screen.getByText("Output")).toBeInTheDocument();
    expect(screen.getByText("All 5 tests passed")).toBeInTheDocument();
  });

  it("returns null when no content and no tool call", () => {
    const { container } = render(
      <MessageRenderer role="assistant" content={null} createdAt={NOW} />,
    );

    expect(container.innerHTML).toBe("");
  });

  it("renders manager message with info styling", () => {
    const { container } = render(
      <MessageRenderer
        role="manager"
        content="Please focus on the auth module."
        createdAt={NOW}
      />,
    );

    expect(
      screen.getByText("Please focus on the auth module."),
    ).toBeInTheDocument();
    // Manager messages use info bg
    const wrapper = container.firstChild as HTMLElement;
    expect(wrapper.className).toContain("flex-row");
  });
});
