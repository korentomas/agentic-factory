import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ManagerChat } from "../manager-chat";

function makeMessage(
  overrides: Partial<{
    id: string;
    content: string;
    sender: "user" | "system";
    createdAt: Date;
  }> = {},
) {
  return {
    id: "msg-1",
    content: "Hello",
    sender: "user" as const,
    createdAt: new Date("2026-02-19T10:00:00Z"),
    ...overrides,
  };
}

describe("ManagerChat", () => {
  it('renders header with "Manager" title', () => {
    render(
      <ManagerChat threadId="t-1" messages={[]} onSend={vi.fn()} />,
    );

    expect(screen.getByText("Manager")).toBeInTheDocument();
    expect(screen.getByText("Guide the agent")).toBeInTheDocument();
  });

  it("shows empty state when no messages", () => {
    render(
      <ManagerChat threadId="t-1" messages={[]} onSend={vi.fn()} />,
    );

    expect(screen.getByText("No messages yet")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Send a message to interrupt or guide the running agent",
      ),
    ).toBeInTheDocument();
  });

  it("renders user messages", () => {
    const messages = [
      makeMessage({ id: "m1", content: "Focus on the auth module", sender: "user" }),
    ];
    render(
      <ManagerChat threadId="t-1" messages={messages} onSend={vi.fn()} />,
    );

    expect(screen.getByText("Focus on the auth module")).toBeInTheDocument();
  });

  it("renders system messages", () => {
    const messages = [
      makeMessage({
        id: "m2",
        content: "Agent acknowledged your request",
        sender: "system",
      }),
    ];
    render(
      <ManagerChat threadId="t-1" messages={messages} onSend={vi.fn()} />,
    );

    expect(
      screen.getByText("Agent acknowledged your request"),
    ).toBeInTheDocument();
  });

  it("calls onSend when form submitted with text", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <ManagerChat threadId="t-1" messages={[]} onSend={onSend} />,
    );

    const input = screen.getByPlaceholderText(
      "Send a message to the agent...",
    );
    await user.type(input, "Stop working on that");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(onSend).toHaveBeenCalledWith("Stop working on that");
  });

  it("input is disabled when disabled prop is true", () => {
    render(
      <ManagerChat
        threadId="t-1"
        messages={[]}
        onSend={vi.fn()}
        disabled
      />,
    );

    const input = screen.getByPlaceholderText("Task is not running");
    expect(input).toBeDisabled();

    const button = screen.getByRole("button", { name: /send message/i });
    expect(button).toBeDisabled();
  });

  it("clears input after sending", async () => {
    const user = userEvent.setup();
    render(
      <ManagerChat threadId="t-1" messages={[]} onSend={vi.fn()} />,
    );

    const input = screen.getByPlaceholderText(
      "Send a message to the agent...",
    );
    await user.type(input, "Fix the tests");
    await user.click(screen.getByRole("button", { name: /send message/i }));

    expect(input).toHaveValue("");
  });
});
