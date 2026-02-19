import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TerminalInput } from "../terminal-input";

const REPOS = [
  { fullName: "acme/backend", url: "https://github.com/acme/backend" },
  { fullName: "acme/frontend", url: "https://github.com/acme/frontend" },
];

describe("TerminalInput", () => {
  it("renders the terminal input form", () => {
    render(<TerminalInput repos={REPOS} onSubmit={vi.fn()} />);

    expect(
      screen.getByPlaceholderText("Describe the task for the agent..."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /submit task/i }),
    ).toBeInTheDocument();
  });

  it("shows the repo selector with provided repos", () => {
    render(<TerminalInput repos={REPOS} onSubmit={vi.fn()} />);

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[0]).toHaveTextContent("acme/backend");
    expect(options[1]).toHaveTextContent("acme/frontend");
  });

  it("shows branch input with default value", () => {
    render(<TerminalInput repos={REPOS} onSubmit={vi.fn()} />);

    const branchInput = screen.getByDisplayValue("main");
    expect(branchInput).toBeInTheDocument();
  });

  it("submit button is disabled when textarea is empty", () => {
    render(<TerminalInput repos={REPOS} onSubmit={vi.fn()} />);

    const button = screen.getByRole("button", { name: /submit task/i });
    expect(button).toBeDisabled();
  });

  it("calls onSubmit with correct data when form submitted", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<TerminalInput repos={REPOS} onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText(
      "Describe the task for the agent...",
    );
    await user.type(textarea, "Fix the login bug");

    const button = screen.getByRole("button", { name: /submit task/i });
    await user.click(button);

    expect(onSubmit).toHaveBeenCalledWith({
      repoUrl: "https://github.com/acme/backend",
      branch: "main",
      title: "Fix the login bug",
      description: "Fix the login bug",
    });
  });

  it("Cmd+Enter keyboard shortcut triggers submit", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<TerminalInput repos={REPOS} onSubmit={onSubmit} />);

    const textarea = screen.getByPlaceholderText(
      "Describe the task for the agent...",
    );
    await user.type(textarea, "Add unit tests");
    await user.keyboard("{Meta>}{Enter}{/Meta}");

    expect(onSubmit).toHaveBeenCalledOnce();
  });

  it("shows text input for repo URL when no repos provided", () => {
    render(<TerminalInput repos={[]} onSubmit={vi.fn()} />);

    const input = screen.getByPlaceholderText("https://github.com/owner/repo");
    expect(input).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("submits with manually typed repo URL", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    render(<TerminalInput repos={[]} onSubmit={onSubmit} />);

    const repoInput = screen.getByPlaceholderText("https://github.com/owner/repo");
    await user.type(repoInput, "https://github.com/test/repo");

    const textarea = screen.getByPlaceholderText("Describe the task for the agent...");
    await user.type(textarea, "Fix the bug");

    const button = screen.getByRole("button", { name: /submit task/i });
    await user.click(button);

    expect(onSubmit).toHaveBeenCalledWith({
      repoUrl: "https://github.com/test/repo",
      branch: "main",
      title: "Fix the bug",
      description: "Fix the bug",
    });
  });

  it("submit button disabled when disabled prop is true", async () => {
    const user = userEvent.setup();
    render(<TerminalInput repos={REPOS} onSubmit={vi.fn()} disabled />);

    const textarea = screen.getByPlaceholderText(
      "Describe the task for the agent...",
    );
    // textarea is also disabled — type should be a no-op,
    // but let's verify the button stays disabled
    expect(textarea).toBeDisabled();

    const button = screen.getByRole("button", { name: /submit task/i });
    expect(button).toBeDisabled();
  });
});
