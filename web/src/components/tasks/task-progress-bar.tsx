"use client";

import { cn } from "@/lib/utils";

interface TaskProgressBarProps {
  steps: Array<{
    title: string;
    description: string;
    status: "pending" | "in_progress" | "completed" | "skipped";
  }>;
  onStepClick?: (index: number) => void;
}

const STEP_COLORS: Record<string, string> = {
  completed: "bg-[var(--color-success)]",
  in_progress: "bg-primary animate-pulse",
  skipped: "bg-[var(--color-warning)]",
  pending: "bg-border",
};

export function TaskProgressBar({ steps, onStepClick }: TaskProgressBarProps) {
  const completed = steps.filter((s) => s.status === "completed").length;
  const total = steps.length;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div>
      {/* Label */}
      <div className="mb-2 flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          <span className="font-medium text-foreground">{completed}</span>{" "}
          of {total} steps completed
        </p>
        <p className="text-xs font-medium text-muted-foreground">
          {percent}%
        </p>
      </div>

      {/* Segments */}
      <div className="flex overflow-hidden rounded-full">
        {steps.map((step, i) => (
          <button
            key={i}
            type="button"
            onClick={() => onStepClick?.(i)}
            title={step.title}
            aria-label={`${step.title}: ${step.status}`}
            className={cn(
              "h-2 flex-1 transition-colors",
              STEP_COLORS[step.status],
              i > 0 && "ml-0.5",
              onStepClick && "cursor-pointer hover:opacity-80",
              !onStepClick && "cursor-default",
            )}
          />
        ))}
      </div>
    </div>
  );
}
