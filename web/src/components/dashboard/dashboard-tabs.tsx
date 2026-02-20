"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import type { ReactNode } from "react";

export type TabId = "overview" | "prs" | "engines" | "learning" | "chat";

const TABS: { id: TabId; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "prs", label: "Pull Requests" },
  { id: "engines", label: "Engines" },
  { id: "learning", label: "Learning" },
  { id: "chat", label: "Chat" },
];

interface DashboardTabsProps {
  children: Record<TabId, ReactNode>;
}

export function DashboardTabs({ children }: DashboardTabsProps) {
  const searchParams = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const rawTab = searchParams.get("tab");
  const activeTab: TabId = TABS.some((t) => t.id === rawTab)
    ? (rawTab as TabId)
    : "overview";

  function handleTabClick(tabId: TabId) {
    const params = new URLSearchParams(searchParams.toString());
    params.set("tab", tabId);
    router.push(`${pathname}?${params.toString()}`, { scroll: false });
  }

  return (
    <div>
      <div
        role="tablist"
        aria-label="Dashboard sections"
        className="mb-6 flex gap-1 overflow-x-auto border-b border-border"
      >
        {TABS.map((tab) => {
          const isActive = tab.id === activeTab;
          return (
            <button
              key={tab.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`tabpanel-${tab.id}`}
              id={`tab-${tab.id}`}
              onClick={() => handleTabClick(tab.id)}
              className={`whitespace-nowrap border-b-2 px-4 py-3 text-sm font-medium transition-colors ${
                isActive
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:border-border hover:text-muted-foreground"
              }`}
            >
              {tab.label}
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`tabpanel-${activeTab}`}
        aria-labelledby={`tab-${activeTab}`}
      >
        {children[activeTab]}
      </div>
    </div>
  );
}
