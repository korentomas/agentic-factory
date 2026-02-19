import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DashboardTabs } from "../dashboard-tabs";
import type { TabId } from "../dashboard-tabs";

const mockPush = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock("next/navigation", () => ({
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ push: mockPush }),
  usePathname: () => "/dashboard",
}));

const children: Record<TabId, React.ReactNode> = {
  overview: <div>Overview content</div>,
  prs: <div>PR content</div>,
  engines: <div>Engines content</div>,
  learning: <div>Learning content</div>,
  chat: <div>Chat content</div>,
};

describe("DashboardTabs", () => {
  beforeEach(() => {
    mockPush.mockClear();
    mockSearchParams = new URLSearchParams();
  });

  it("renders all 5 tab buttons", () => {
    render(<DashboardTabs>{children}</DashboardTabs>);

    expect(screen.getByRole("tab", { name: "Overview" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Pull Requests" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Engines" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Learning" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Chat" })).toBeInTheDocument();
  });

  it("overview tab is active by default", () => {
    render(<DashboardTabs>{children}</DashboardTabs>);

    const overviewTab = screen.getByRole("tab", { name: "Overview" });
    expect(overviewTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Overview content")).toBeInTheDocument();
  });

  it("clicking a tab calls router.push with correct params", async () => {
    const user = userEvent.setup();
    render(<DashboardTabs>{children}</DashboardTabs>);

    await user.click(screen.getByRole("tab", { name: "Pull Requests" }));

    expect(mockPush).toHaveBeenCalledWith(
      "/dashboard?tab=prs",
      { scroll: false },
    );
  });

  it("renders correct content for active tab from search params", () => {
    mockSearchParams = new URLSearchParams("tab=engines");
    render(<DashboardTabs>{children}</DashboardTabs>);

    const enginesTab = screen.getByRole("tab", { name: "Engines" });
    expect(enginesTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Engines content")).toBeInTheDocument();
  });

  it("falls back to overview for invalid tab param", () => {
    mockSearchParams = new URLSearchParams("tab=invalid");
    render(<DashboardTabs>{children}</DashboardTabs>);

    const overviewTab = screen.getByRole("tab", { name: "Overview" });
    expect(overviewTab).toHaveAttribute("aria-selected", "true");
    expect(screen.getByText("Overview content")).toBeInTheDocument();
  });

  it("renders tablist with correct role", () => {
    render(<DashboardTabs>{children}</DashboardTabs>);

    expect(screen.getByRole("tablist")).toBeInTheDocument();
  });

  it("renders tabpanel with correct role", () => {
    render(<DashboardTabs>{children}</DashboardTabs>);

    expect(screen.getByRole("tabpanel")).toBeInTheDocument();
  });
});
