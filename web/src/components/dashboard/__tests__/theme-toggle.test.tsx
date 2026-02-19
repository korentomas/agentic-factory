import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeToggle } from "../../theme-toggle";

beforeEach(() => {
  localStorage.removeItem("theme");
  document.documentElement.removeAttribute("data-theme");
});

describe("ThemeToggle", () => {
  it("renders a button with aria-label", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button", {
      name: /switch theme/i,
    });
    expect(button).toBeInTheDocument();
  });

  it("defaults to system theme", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button");
    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: system)"
    );
  });

  it("cycles through themes on clicks: system -> light -> dark -> system", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button");

    // Default: system
    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: system)"
    );

    // Click 1: system -> light
    fireEvent.click(button);
    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: light)"
    );
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");

    // Click 2: light -> dark
    fireEvent.click(button);
    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: dark)"
    );
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");

    // Click 3: dark -> system
    fireEvent.click(button);
    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: system)"
    );
  });

  it("persists theme to localStorage", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button");
    fireEvent.click(button); // system -> light

    expect(localStorage.getItem("theme")).toBe("light");
  });

  it("restores theme from localStorage", () => {
    localStorage.setItem("theme", "dark");
    render(<ThemeToggle />);

    const button = screen.getByRole("button");
    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: dark)"
    );
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
  });
});
