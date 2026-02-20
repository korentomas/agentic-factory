import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ThemeToggle } from "../../theme-toggle";

// Mock next-themes
let mockTheme = "light";
const mockSetTheme = vi.fn((t: string) => {
  mockTheme = t;
});

vi.mock("next-themes", () => ({
  useTheme: () => ({
    theme: mockTheme,
    setTheme: mockSetTheme,
  }),
}));

describe("ThemeToggle", () => {
  beforeEach(() => {
    mockTheme = "light";
    mockSetTheme.mockClear();
  });

  it("renders a button with aria-label", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button", {
      name: /switch theme/i,
    });
    expect(button).toBeInTheDocument();
  });

  it("shows current theme in aria-label", () => {
    render(<ThemeToggle />);

    const button = screen.getByRole("button");
    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: light)"
    );
  });

  it("toggles from light to dark on click", () => {
    mockTheme = "light";
    render(<ThemeToggle />);

    const button = screen.getByRole("button");
    fireEvent.click(button);

    expect(mockSetTheme).toHaveBeenCalledWith("dark");
  });

  it("toggles from dark to light on click", () => {
    mockTheme = "dark";
    render(<ThemeToggle />);

    const button = screen.getByRole("button");

    expect(button).toHaveAttribute(
      "aria-label",
      "Switch theme (current: dark)"
    );

    fireEvent.click(button);
    expect(mockSetTheme).toHaveBeenCalledWith("light");
  });
});
