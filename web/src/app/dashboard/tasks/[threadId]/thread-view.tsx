"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  DollarSign,
  GitCommit,
  ListChecks,
  Loader2,
  GitBranch,
} from "lucide-react";
import { useTaskStream } from "@/hooks/use-task-stream";
import { MessageRenderer } from "@/components/tasks/message-renderer";
import { TaskProgressBar } from "@/components/tasks/task-progress-bar";
import { ManagerChat } from "@/components/tasks/manager-chat";
import { TasksSidebar } from "@/components/tasks/tasks-sidebar";
import { cn } from "@/lib/utils";

interface ThreadViewProps {
  threadId: string;
  initialThread: {
    title: string;
    status: string;
    engine: string | null;
    model: string | null;
    repoUrl: string;
    branch: string;
    costUsd: number;
    durationMs: number;
  };
  initialPlans: Array<{
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

const STATUS_BADGE: Record<string, { label: string; color: string }> = {
  pending: { label: "Pending", color: "bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)]" },
  running: { label: "Running", color: "bg-[var(--color-accent)]/10 text-[var(--color-accent)]" },
  committing: { label: "Committing", color: "bg-[var(--color-info)]/10 text-[var(--color-info)]" },
  complete: { label: "Complete", color: "bg-[var(--color-success)]/10 text-[var(--color-success)]" },
  failed: { label: "Failed", color: "bg-[var(--color-error)]/10 text-[var(--color-error)]" },
  cancelled: { label: "Cancelled", color: "bg-[var(--color-warning)]/10 text-[var(--color-warning)]" },
};

function formatCost(usd: number | string | null | undefined): string {
  const n = typeof usd === "string" ? parseFloat(usd) : (usd ?? 0);
  if (n === 0) return "$0.00";
  if (n < 0.01) return "<$0.01";
  return `$${n.toFixed(2)}`;
}

function formatDuration(ms: number | null | undefined): string {
  if (!ms || ms === 0) return "--";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}m`;
}

export function ThreadView({
  threadId,
  initialThread,
  initialPlans,
}: ThreadViewProps) {
  const { messages, threadStatus, isConnected, isComplete } = useTaskStream(threadId);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [managerMessages, setManagerMessages] = useState<
    Array<{ id: string; content: string; sender: "user" | "system"; createdAt: Date }>
  >([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Derive current status from SSE or fallback to initial
  const currentStatus = threadStatus?.status ?? initialThread.status;
  const isRunning = currentStatus === "running" || currentStatus === "committing";
  const badge = STATUS_BADGE[currentStatus] ?? STATUS_BADGE.pending;
  const commitSha = threadStatus?.commitSha;
  const costUsd = threadStatus?.costUsd ?? initialThread.costUsd;
  const durationMs = threadStatus?.durationMs ?? initialThread.durationMs;

  // Latest plan steps for progress bar
  const latestPlan = initialPlans.length > 0
    ? initialPlans[initialPlans.length - 1]
    : null;

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Handle manager chat send
  const handleManagerSend = useCallback(
    async (content: string) => {
      const optimisticId = `opt-${Date.now()}`;
      setManagerMessages((prev) => [
        ...prev,
        { id: optimisticId, content, sender: "user", createdAt: new Date() },
      ]);

      try {
        const res = await fetch(`/api/tasks/${threadId}/interrupt`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        });

        if (!res.ok) {
          const err = await res.json();
          setManagerMessages((prev) => [
            ...prev,
            {
              id: `sys-${Date.now()}`,
              content: `Failed to send: ${err.error ?? "Unknown error"}`,
              sender: "system",
              createdAt: new Date(),
            },
          ]);
        }
      } catch {
        setManagerMessages((prev) => [
          ...prev,
          {
            id: `sys-${Date.now()}`,
            content: "Network error. Message not delivered.",
            sender: "system",
            createdAt: new Date(),
          },
        ]);
      }
    },
    [threadId],
  );

  return (
    <div>
      {/* Header bar */}
      <div className="mb-[var(--space-6)] flex flex-wrap items-center gap-[var(--space-3)]">
        <Link
          href="/dashboard/tasks"
          className="rounded-[var(--radius-md)] p-[var(--space-2)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-text)]"
          aria-label="Back to tasks"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-[var(--text-xl)] font-semibold text-[var(--color-text)]">
            {threadStatus?.title ?? initialThread.title}
          </h1>
          <div className="mt-[var(--space-1)] flex flex-wrap items-center gap-[var(--space-3)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
            <span className="inline-flex items-center gap-[var(--space-1)]">
              <GitBranch className="h-3 w-3" />
              <span className="font-mono">{initialThread.branch}</span>
            </span>

            {(threadStatus?.engine ?? initialThread.engine) && (
              <span className="rounded-full border border-[var(--color-border-strong)] bg-[var(--color-bg-secondary)] px-[var(--space-2)] py-0.5 font-mono text-[10px]">
                {threadStatus?.engine ?? initialThread.engine}
              </span>
            )}

            {commitSha && (
              <span className="inline-flex items-center gap-[var(--space-1)]">
                <GitCommit className="h-3 w-3" />
                <span className="font-mono">{commitSha.slice(0, 7)}</span>
              </span>
            )}

            <span className="inline-flex items-center gap-[var(--space-1)]">
              <DollarSign className="h-3 w-3" />
              {formatCost(costUsd)}
            </span>

            <span>{formatDuration(durationMs)}</span>
          </div>
        </div>

        {/* Status badge */}
        <div className="flex items-center gap-[var(--space-3)]">
          <span
            className={cn(
              "inline-flex items-center gap-[var(--space-1)] rounded-full px-[var(--space-3)] py-[var(--space-1)] text-[var(--text-xs)] font-medium",
              badge.color,
            )}
          >
            {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
            {badge.label}
          </span>

          {initialPlans.length > 0 && (
            <button
              type="button"
              onClick={() => setSidebarOpen(true)}
              className="rounded-[var(--radius-md)] p-[var(--space-2)] text-[var(--color-text-muted)] transition-colors hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-text)]"
              aria-label="Open task plan"
            >
              <ListChecks className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {latestPlan && latestPlan.steps.length > 0 && (
        <div className="mb-[var(--space-6)]">
          <TaskProgressBar
            steps={latestPlan.steps}
            onStepClick={() => setSidebarOpen(true)}
          />
        </div>
      )}

      {/* Main content: messages + manager chat */}
      <div className="flex gap-[var(--space-6)]">
        {/* Message stream */}
        <div className="min-w-0 flex-1">
          <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)]">
            {/* Stream header */}
            <div className="flex items-center justify-between border-b border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-3)]">
              <p className="text-[var(--text-sm)] font-medium text-[var(--color-text)]">
                Execution Log
              </p>
              <div className="flex items-center gap-[var(--space-2)]">
                {isConnected && isRunning && (
                  <span className="flex items-center gap-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-accent)]">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-[var(--color-accent)]" />
                    Live
                  </span>
                )}
                {isComplete && (
                  <span className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
                    Finished
                  </span>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="max-h-[600px] overflow-y-auto">
              {messages.length === 0 && (
                <div className="flex items-center justify-center py-[var(--space-12)]">
                  {isRunning ? (
                    <div className="text-center">
                      <Loader2 className="mx-auto h-8 w-8 animate-spin text-[var(--color-accent)]" />
                      <p className="mt-[var(--space-3)] text-[var(--text-sm)] text-[var(--color-text-muted)]">
                        Waiting for agent output...
                      </p>
                    </div>
                  ) : (
                    <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
                      No messages yet.
                    </p>
                  )}
                </div>
              )}

              {messages.map((msg) => (
                <MessageRenderer
                  key={msg.id}
                  role={msg.role}
                  content={msg.content}
                  toolName={msg.toolName}
                  toolInput={msg.toolInput}
                  toolOutput={msg.toolOutput}
                  createdAt={msg.createdAt}
                />
              ))}
              <div ref={messagesEndRef} />
            </div>
          </div>

          {/* Error message */}
          {threadStatus?.errorMessage && (
            <div className="mt-[var(--space-4)] rounded-[var(--radius-lg)] border border-[var(--color-error)]/20 bg-[var(--color-error)]/5 px-[var(--space-4)] py-[var(--space-3)]">
              <p className="text-[var(--text-sm)] font-medium text-[var(--color-error)]">
                Error
              </p>
              <p className="mt-[var(--space-1)] text-[var(--text-sm)] text-[var(--color-text-secondary)]">
                {threadStatus.errorMessage}
              </p>
            </div>
          )}
        </div>

        {/* Manager chat (hidden on mobile) */}
        <div className="hidden w-80 shrink-0 lg:block">
          <div className="sticky top-[var(--space-4)]" style={{ height: "calc(100vh - 300px)" }}>
            <ManagerChat
              threadId={threadId}
              messages={managerMessages}
              disabled={!isRunning}
              onSend={handleManagerSend}
            />
          </div>
        </div>
      </div>

      {/* Tasks sidebar */}
      <TasksSidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        plans={initialPlans}
      />
    </div>
  );
}
