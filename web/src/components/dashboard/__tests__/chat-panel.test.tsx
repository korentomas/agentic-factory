import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "../chat-panel";

const mockSendMessage = vi.fn();

let mockReturn: {
  messages: Array<{
    id: string;
    role: string;
    parts: Array<{ type: string; text?: string }>;
  }>;
  sendMessage: typeof mockSendMessage;
  status: "ready" | "submitted" | "streaming" | "error";
  error: undefined | Error;
};

vi.mock("@ai-sdk/react", () => ({
  useChat: () => mockReturn,
}));

beforeEach(() => {
  mockSendMessage.mockClear();
  mockReturn = {
    messages: [],
    sendMessage: mockSendMessage,
    status: "ready",
    error: undefined,
  };
});

describe("ChatPanel", () => {
  it("renders empty state with placeholder text", () => {
    render(<ChatPanel />);

    expect(screen.getByText("Talk to your codebase")).toBeInTheDocument();
    expect(
      screen.getByText(
        "Ask questions, review code, or type /task to dispatch work",
      ),
    ).toBeInTheDocument();
  });

  it("renders input field and send button", () => {
    render(<ChatPanel />);

    expect(
      screen.getByPlaceholderText(
        "Ask about your code, or /task to dispatch...",
      ),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /send/i })).toBeInTheDocument();
  });

  it("disables send button when input is empty", () => {
    render(<ChatPanel />);

    const button = screen.getByRole("button", { name: /send/i });
    expect(button).toBeDisabled();
  });

  it("enables send button when input has text", async () => {
    const user = userEvent.setup();
    render(<ChatPanel />);

    const input = screen.getByPlaceholderText(
      "Ask about your code, or /task to dispatch...",
    );
    await user.type(input, "hello");

    const button = screen.getByRole("button", { name: /send/i });
    expect(button).not.toBeDisabled();
  });

  it("renders messages from the hook", () => {
    mockReturn.messages = [
      {
        id: "1",
        role: "user",
        parts: [{ type: "text", text: "What does main.py do?" }],
      },
      {
        id: "2",
        role: "assistant",
        parts: [{ type: "text", text: "It starts the FastAPI server." }],
      },
    ];

    render(<ChatPanel />);

    expect(screen.getByText("What does main.py do?")).toBeInTheDocument();
    expect(
      screen.getByText("It starts the FastAPI server."),
    ).toBeInTheDocument();
    expect(
      screen.queryByText("Talk to your codebase"),
    ).not.toBeInTheDocument();
  });

  it("shows loading indicator when status is streaming", () => {
    mockReturn.status = "streaming";

    const { container } = render(<ChatPanel />);

    const dots = container.querySelectorAll(".animate-bounce");
    expect(dots.length).toBe(3);
  });

  it("disables send button when loading", async () => {
    const user = userEvent.setup();
    mockReturn.status = "submitted";

    render(<ChatPanel />);

    const input = screen.getByPlaceholderText(
      "Ask about your code, or /task to dispatch...",
    );
    await user.type(input, "hello");

    const button = screen.getByRole("button", { name: /send/i });
    expect(button).toBeDisabled();
  });
});
