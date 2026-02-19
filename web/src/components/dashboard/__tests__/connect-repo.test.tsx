import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConnectRepo } from "../connect-repo";

describe("ConnectRepo", () => {
  it("renders the heading", () => {
    render(<ConnectRepo />);

    expect(
      screen.getByText("Connect your first repository")
    ).toBeInTheDocument();
  });

  it("renders the description text", () => {
    render(<ConnectRepo />);

    expect(
      screen.getByText(
        /Install the LailaTov GitHub App on your repository to start turning issues into pull requests automatically/
      )
    ).toBeInTheDocument();
  });

  it("has a link to GitHub App installation", () => {
    render(<ConnectRepo />);

    const link = screen.getByRole("link", { name: "Install GitHub App" });
    expect(link).toHaveAttribute(
      "href",
      "https://github.com/apps/agentfactory-bot/installations/new"
    );
  });

  it("renders the link as visible text", () => {
    render(<ConnectRepo />);

    expect(screen.getByText("Install GitHub App")).toBeInTheDocument();
  });

  it("renders within a section element", () => {
    const { container } = render(<ConnectRepo />);

    const section = container.querySelector("section");
    expect(section).toBeTruthy();
  });

  it("heading is an h2 element", () => {
    render(<ConnectRepo />);

    const heading = screen.getByRole("heading", {
      name: "Connect your first repository",
    });
    expect(heading.tagName).toBe("H2");
  });
});
