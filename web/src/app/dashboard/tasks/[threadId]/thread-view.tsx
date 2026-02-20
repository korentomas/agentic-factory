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
  pending: { label: "Pending", color: "bg-muted text-muted-foreground" },
  running: { label: "Running", color: "bg-primary/10 text-primary" },
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
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <Link
          href="/dashboard/tasks"
          className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
          aria-label="Back to tasks"
        >
          <ArrowLeft className="h-5 w-5" />
        </Link>

        <div className="min-w-0 flex-1">
          <h1 className="truncate text-xl font-semibold text-foreground">
            {threadStatus?.title ?? initialThread.title}
          </h1>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
            <span className="inline-flex items-center gap-1">
              <GitBranch className="h-3 w-3" />
              <span className="font-mono">{initialThread.branch}</span>
            </span>

            {(threadStatus?.engine ?? initialThread.engine) && (
              <span className="rounded-full border border-border bg-muted px-2 py-0.5 font-mono text-[10px]">
                {threadStatus?.engine ?? initialThread.engine}
              </span>
            )}

            {commitSha && (
              <span className="inline-flex items-center gap-1">
                <GitCommit className="h-3 w-3" />
                <span className="font-mono">{commitSha.slice(0, 7)}</span>
              </span>
            )}

            <span className="inline-flex items-center gap-1">
              <DollarSign className="h-3 w-3" />
              {formatCost(costUsd)}
            </span>

            <span>{formatDuration(durationMs)}</span>
          </div>
        </div>

        {/* Status badge */}
        <div className="flex items-center gap-3">
          <span
            className={cn(
              "inline-flex items-center gap-1 rounded-full px-3 py-1 text-xs font-medium",
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
              className="rounded-md p-2 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
              aria-label="Open task plan"
            >
              <ListChecks className="h-5 w-5" />
            </button>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {latestPlan && latestPlan.steps.length > 0 && (
        <div className="mb-6">
          <TaskProgressBar
            steps={latestPlan.steps}
            onStepClick={() => setSidebarOpen(true)}
          />
        </div>
      )}

      {/* Main content: messages + manager chat */}
      <div className="flex gap-6">
        {/* Message stream */}
        <div className="min-w-0 flex-1">
          <div className="rounded-lg border border-border bg-card">
            {/* Stream header */}
            <div className="flex items-center justify-between border-b border-border px-4 py-3">
              <p className="text-sm font-medium text-foreground">
                Execution Log
              </p>
              <div className="flex items-center gap-2">
                {isConnected && isRunning && (
                  <span className="flex items-center gap-1 text-xs text-primary">
                    <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
                    Live
                  </span>
                )}
                {isComplete && (
                  <span className="text-xs text-muted-foreground">
                    Finished
                  </span>
                )}
              </div>
            </div>

            {/* Messages */}
            <div className="max-h-[600px] overflow-y-auto">
              {messages.length === 0 && (
                <div className="flex items-center justify-center py-12">
                  {isRunning ? (
                    <div className="text-center">
                      <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" />
                      <p className="mt-3 text-sm text-muted-foreground">
                        Waiting for agent output...
                      </p>
                    </div>
                  ) : (
                    <p className="text-sm text-muted-foreground">
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
            <div className="mt-4 rounded-lg border border-[var(--color-error)]/20 bg-[var(--color-error)]/5 px-4 py-3">
              <p className="text-sm font-medium text-[var(--color-error)]">
                Error
              </p>
              <p className="mt-1 text-sm text-muted-foreground">
                {threadStatus.errorMessage}
              </p>
            </div>
          )}
        </div>

        {/* Manager chat (hidden on mobile) */}
        <div className="hidden w-80 shrink-0 lg:block">
          <div className="sticky top-4" style={{ height: "calc(100vh - 300px)" }}>
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
