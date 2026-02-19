"use client";

import { useState, useMemo } from "react";
import {
  X,
  ChevronLeft,
  ChevronRight,
  CheckCircle2,
  Play,
  Circle,
  SkipForward,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface TasksSidebarProps {
  open: boolean;
  onClose: () => void;
  plans: Array<{
    revision: number;
    steps: Array<{
      title: string;
      description: string;
      status: "pending" | "in_progress" | "completed" | "skipped";
    }>;
    createdBy: string;
    createdAt: Date;
  }>;
}

type FilterType = "all" | "completed" | "current" | "pending";

const STEP_ICONS: Record<
  string,
  { icon: typeof CheckCircle2; color: string }
> = {
  completed: {
    icon: CheckCircle2,
    color: "text-[var(--color-success)]",
  },
  in_progress: {
    icon: Play,
    color: "text-[var(--color-accent)]",
  },
  pending: {
    icon: Circle,
    color: "text-[var(--color-text-muted)]",
  },
  skipped: {
    icon: SkipForward,
    color: "text-[var(--color-warning)]",
  },
};

const FILTERS: Array<{ key: FilterType; label: string }> = [
  { key: "all", label: "All" },
  { key: "completed", label: "Completed" },
  { key: "current", label: "Current" },
  { key: "pending", label: "Pending" },
];

export function TasksSidebar({ open, onClose, plans }: TasksSidebarProps) {
  const [revisionIndex, setRevisionIndex] = useState(0);
  const [filter, setFilter] = useState<FilterType>("all");

  const currentPlan = plans[revisionIndex];
  const hasMultipleRevisions = plans.length > 1;

  const filteredSteps = useMemo(() => {
    if (!currentPlan) return [];
    if (filter === "all") return currentPlan.steps;
    if (filter === "current")
      return currentPlan.steps.filter((s) => s.status === "in_progress");
    return currentPlan.steps.filter((s) => s.status === filter);
  }, [currentPlan, filter]);

  return (
    <>
      {/* Backdrop */}
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/20"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      {/* Panel */}
      <div
        className={cn(
          "fixed top-0 right-0 z-50 flex h-full w-80 flex-col border-l border-[var(--color-border)] bg-[var(--color-bg-surface)] shadow-[var(--shadow-lg)] transition-transform sm:w-96",
          open ? "translate-x-0" : "translate-x-full",
        )}
        style={{
          transitionDuration: "var(--duration-normal)",
          transitionTimingFunction: "var(--ease-out)",
        }}
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-3)]">
          <h2 className="text-[var(--text-sm)] font-medium text-[var(--color-text)]">
            Task Plan
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close sidebar"
            className="rounded-[var(--radius-sm)] p-[var(--space-1)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-text)]"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Revision navigation */}
        {hasMultipleRevisions && currentPlan && (
          <div className="flex items-center justify-between border-b border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-2)]">
            <button
              type="button"
              onClick={() => setRevisionIndex(Math.max(0, revisionIndex - 1))}
              disabled={revisionIndex === 0}
              aria-label="Previous revision"
              className="rounded-[var(--radius-sm)] p-[var(--space-1)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-secondary)] disabled:opacity-40"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
            <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
              Revision {currentPlan.revision} of {plans.length}
            </p>
            <button
              type="button"
              onClick={() =>
                setRevisionIndex(Math.min(plans.length - 1, revisionIndex + 1))
              }
              disabled={revisionIndex === plans.length - 1}
              aria-label="Next revision"
              className="rounded-[var(--radius-sm)] p-[var(--space-1)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-secondary)] disabled:opacity-40"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-[var(--space-1)] border-b border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-2)]">
          {FILTERS.map((f) => (
            <button
              key={f.key}
              type="button"
              onClick={() => setFilter(f.key)}
              className={cn(
                "rounded-full px-[var(--space-3)] py-[var(--space-1)] text-[var(--text-xs)] font-medium transition-colors",
                filter === f.key
                  ? "bg-[var(--color-accent)] text-[var(--color-text-inverse)]"
                  : "bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)] hover:text-[var(--color-text)]",
              )}
            >
              {f.label}
            </button>
          ))}
        </div>

        {/* Step list */}
        <div className="flex-1 overflow-y-auto px-[var(--space-4)] py-[var(--space-3)]">
          {!currentPlan && (
            <p className="py-[var(--space-8)] text-center text-[var(--text-sm)] text-[var(--color-text-muted)]">
              No plan yet
            </p>
          )}

          {filteredSteps.length === 0 && currentPlan && (
            <p className="py-[var(--space-8)] text-center text-[var(--text-sm)] text-[var(--color-text-muted)]">
              No steps match this filter
            </p>
          )}

          {filteredSteps.map((step, i) => {
            const stepConfig = STEP_ICONS[step.status] ?? STEP_ICONS.pending;
            const StepIcon = stepConfig.icon;

            return (
              <div
                key={i}
                className="flex gap-[var(--space-3)] py-[var(--space-3)]"
              >
                <StepIcon
                  className={cn("mt-0.5 h-4 w-4 shrink-0", stepConfig.color)}
                />
                <div className="min-w-0">
                  <p className="text-[var(--text-sm)] font-medium text-[var(--color-text)]">
                    {step.title}
                  </p>
                  <p className="mt-[var(--space-1)] text-[var(--text-xs)] leading-relaxed text-[var(--color-text-muted)]">
                    {step.description}
                  </p>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer */}
        {currentPlan && (
          <div className="border-t border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-3)]">
            <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
              Created by{" "}
              <span className="font-mono">{currentPlan.createdBy}</span>{" "}
              &middot;{" "}
              {currentPlan.createdAt.toLocaleDateString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
              })}
            </p>
          </div>
        )}
      </div>
    </>
  );
}
