"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Terminal } from "lucide-react";
import { TerminalInput } from "@/components/tasks/terminal-input";
import { ThreadCard } from "@/components/tasks/thread-card";
import type { TaskThreadSummary } from "@/lib/tasks/types";

interface TasksPageClientProps {
  threads: TaskThreadSummary[];
  repos: Array<{ fullName: string; url: string }>;
}

export function TasksPageClient({ threads, repos }: TasksPageClientProps) {
  const router = useRouter();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const activeThreads = threads.filter(
    (t) => t.status === "running" || t.status === "pending" || t.status === "committing",
  );
  const recentThreads = threads.filter(
    (t) => t.status !== "running" && t.status !== "pending" && t.status !== "committing",
  );

  const handleSubmit = useCallback(
    async (task: {
      repoUrl: string;
      branch: string;
      title: string;
      description: string;
    }) => {
      setIsSubmitting(true);
      try {
        const res = await fetch("/api/tasks/create", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(task),
        });

        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.error ?? "Failed to create task");
        }

        const data = await res.json();
        router.push(`/dashboard/tasks/${data.threadId}`);
      } catch {
        // Let the user retry
        setIsSubmitting(false);
      }
    },
    [router],
  );

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">
          Tasks
        </h1>
        <p className="mt-2 text-muted-foreground">
          Create and monitor agent task executions.
        </p>
      </div>

      {/* Terminal input */}
      <div className="mb-8">
        <TerminalInput
          repos={repos}
          onSubmit={handleSubmit}
          disabled={isSubmitting}
        />
      </div>

      {/* Active threads */}
      {activeThreads.length > 0 && (
        <section className="mb-8">
          <h2 className="mb-4 text-lg font-medium text-foreground">
            Active
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {activeThreads.map((thread) => (
              <ThreadCard key={thread.id} thread={thread} />
            ))}
          </div>
        </section>
      )}

      {/* Recent threads */}
      {recentThreads.length > 0 && (
        <section>
          <h2 className="mb-4 text-lg font-medium text-foreground">
            Recent
          </h2>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {recentThreads.map((thread) => (
              <ThreadCard key={thread.id} thread={thread} />
            ))}
          </div>
        </section>
      )}

      {/* Empty state */}
      {threads.length === 0 && (
        <div className="mt-6 rounded-lg border border-dashed border-border p-12 text-center">
          <Terminal className="mx-auto h-10 w-10 text-muted-foreground/40" />
          <p className="mt-4 text-muted-foreground">
            No tasks yet. Describe a task above to get started.
          </p>
        </div>
      )}
    </div>
  );
}
