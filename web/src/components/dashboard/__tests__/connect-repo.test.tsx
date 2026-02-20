import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConnectRepo } from "../connect-repo";

describe("ConnectRepo", () => {
  it("renders the get started heading", () => {
    render(<ConnectRepo />);

    expect(screen.getByRole("heading", { name: "Get started" })).toBeInTheDocument();
  });

  it("shows step progress count", () => {
    render(<ConnectRepo />);

    // Sign in is always done = 1 of 4
    expect(screen.getByText("1 of 4 steps complete")).toBeInTheDocument();
  });

  it("shows install button when no repos connected", () => {
    render(<ConnectRepo repoCount={0} />);

    const installLink = screen.getByRole("link", { name: /Install/ });
    expect(installLink).toHaveAttribute(
      "href",
      "https://github.com/apps/agentfactory-bot/installations/new",
    );
  });

  it("shows repo count when repos are connected", () => {
    render(<ConnectRepo repoCount={3} />);

    expect(screen.getByText("3 repositories connected")).toBeInTheDocument();
  });

  it("shows singular for 1 repo", () => {
    render(<ConnectRepo repoCount={1} />);

    expect(screen.getByText("1 repository connected")).toBeInTheDocument();
  });

  it("shows runner status when connected", () => {
    render(<ConnectRepo hasRunner={true} />);

    expect(screen.getByText("Agent runner is reachable")).toBeInTheDocument();
  });

  it("shows runner not configured when not connected", () => {
    render(<ConnectRepo hasRunner={false} />);

    expect(screen.getByText("Cloud runner not configured yet")).toBeInTheDocument();
  });

  it("shows create task button when all prereqs met", () => {
    render(<ConnectRepo repoCount={1} hasRunner={true} />);

    const link = screen.getByRole("link", { name: "Create your first task" });
    expect(link).toHaveAttribute("href", "/chat");
  });

  it("does not show create task button when prereqs not met", () => {
    render(<ConnectRepo repoCount={0} hasRunner={false} />);

    expect(screen.queryByRole("link", { name: "Create your first task" })).not.toBeInTheDocument();
  });

  it("renders within a section element", () => {
    const { container } = render(<ConnectRepo />);

    const section = container.querySelector("section");
    expect(section).toBeTruthy();
  });

  it("updates progress when repos and runner are connected", () => {
    render(<ConnectRepo repoCount={2} hasRunner={true} />);

    // Sign in + install + runner = 3 of 4
    expect(screen.getByText("3 of 4 steps complete")).toBeInTheDocument();
  });

  it("shows all 4 setup steps", () => {
    render(<ConnectRepo />);

    expect(screen.getByText("Sign in with GitHub")).toBeInTheDocument();
    expect(screen.getByText("Install the GitHub App")).toBeInTheDocument();
    expect(screen.getByText("Runner connected")).toBeInTheDocument();
    expect(screen.getByText("Create your first task")).toBeInTheDocument();
  });

  it("shows error message when syncError is no_token", () => {
    render(<ConnectRepo syncError="no_token" />);

    expect(
      screen.getByText("GitHub token missing — try signing out and back in"),
    ).toBeInTheDocument();
  });

  it("shows error message when syncError is no_installations", () => {
    render(<ConnectRepo syncError="no_installations" />);

    expect(
      screen.getByText("No GitHub App installation found — click Install above"),
    ).toBeInTheDocument();
  });

  it("shows error message when syncError is github_api_401", () => {
    render(<ConnectRepo syncError="github_api_401" />);

    expect(
      screen.getByText("GitHub token expired — sign out and sign in again"),
    ).toBeInTheDocument();
  });

  it("does not show error when repos are connected despite sync error", () => {
    render(<ConnectRepo repoCount={2} syncError="no_installations" />);

    expect(screen.getByText("2 repositories connected")).toBeInTheDocument();
  });
});
