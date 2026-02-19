"use client";

import Link from "next/link";
import {
  GitBranch,
  Clock,
  Loader2,
  CheckCircle2,
  XCircle,
  Ban,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface ThreadCardProps {
  thread: {
    id: string;
    title: string;
    branch: string;
    status: string;
    engine: string | null;
    costUsd: number;
    durationMs: number;
    createdAt: Date;
  };
}

const STATUS_CONFIG: Record<
  string,
  { icon: typeof Clock; label: string; color: string }
> = {
  pending: {
    icon: Clock,
    label: "Pending",
    color: "text-[var(--color-text-muted)]",
  },
  running: {
    icon: Loader2,
    label: "Running",
    color: "text-[var(--color-accent)]",
  },
  committing: {
    icon: Loader2,
    label: "Committing",
    color: "text-[var(--color-info)]",
  },
  complete: {
    icon: CheckCircle2,
    label: "Complete",
    color: "text-[var(--color-success)]",
  },
  failed: {
    icon: XCircle,
    label: "Failed",
    color: "text-[var(--color-error)]",
  },
  cancelled: {
    icon: Ban,
    label: "Cancelled",
    color: "text-[var(--color-warning)]",
  },
};

function timeAgo(date: Date): string {
  const now = Date.now();
  const then = date.getTime();
  const diff = now - then;

  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatDuration(ms: number): string {
  if (ms === 0) return "--";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}m`;
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0";
  if (usd < 0.01) return "<$0.01";
  return `$${usd.toFixed(2)}`;
}

export function ThreadCard({ thread }: ThreadCardProps) {
  const config = STATUS_CONFIG[thread.status] ?? STATUS_CONFIG.pending;
  const StatusIcon = config.icon;
  const isSpinning = thread.status === "running" || thread.status === "committing";

  return (
    <Link
      href={`/dashboard/tasks/${thread.id}`}
      className="block rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-4)] shadow-[var(--shadow-sm)] transition-shadow hover:shadow-[var(--shadow-md)]"
    >
      <div className="flex items-start justify-between gap-[var(--space-3)]">
        {/* Left side */}
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-[var(--text-sm)] font-medium text-[var(--color-text)]">
            {thread.title}
          </h3>

          <div className="mt-[var(--space-2)] flex flex-wrap items-center gap-[var(--space-3)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
            <span className="inline-flex items-center gap-[var(--space-1)]">
              <GitBranch className="h-3 w-3" />
              <span className="font-mono">{thread.branch}</span>
            </span>

            {thread.engine && (
              <span className="rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-secondary)] px-[var(--space-2)] py-0.5 font-mono text-[10px]">
                {thread.engine}
              </span>
            )}

            <span>{formatDuration(thread.durationMs)}</span>
            <span>{formatCost(thread.costUsd)}</span>
          </div>
        </div>

        {/* Right side — status */}
        <div className={cn("flex shrink-0 items-center gap-[var(--space-1)]", config.color)}>
          <StatusIcon
            className={cn("h-4 w-4", isSpinning && "animate-spin")}
          />
          <span className="text-[var(--text-xs)] font-medium">
            {config.label}
          </span>
        </div>
      </div>

      {/* Footer */}
      <p className="mt-[var(--space-2)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
        {timeAgo(thread.createdAt)}
      </p>
    </Link>
  );
}
