"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Search, Filter, Plus } from "lucide-react";
import Link from "next/link";
import { ThreadCard, ThreadCardLoading } from "@/components/v2/thread-card";
import { AppHeader } from "@/components/v2/app-header";
import { toThreadMetadata, fetcher } from "@/components/v2/thread-data";
import type { TaskThreadRow } from "@/components/v2/thread-data";
import type { ThreadStatus } from "@/components/v2/types";
import { cn } from "@/lib/utils";

type FilterStatus = "all" | ThreadStatus;

const FILTER_STATUSES: FilterStatus[] = [
  "all",
  "running",
  "complete",
  "failed",
  "pending",
  "committing",
  "cancelled",
];

export default function ThreadsPage() {
  const { data, isLoading } = useSWR<{ threads: TaskThreadRow[] }>(
    "/api/tasks",
    fetcher,
    { refreshInterval: 10000 },
  );

  const [searchQuery, setSearchQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<FilterStatus>("all");

  const threads = useMemo(
    () => (data?.threads ?? []).map(toThreadMetadata),
    [data],
  );

  const statusCounts = useMemo(() => {
    const counts: Record<FilterStatus, number> = {
      all: threads.length,
      pending: 0,
      running: 0,
      committing: 0,
      complete: 0,
      failed: 0,
      cancelled: 0,
    };
    for (const t of threads) {
      if (t.status in counts) {
        counts[t.status as FilterStatus]++;
      }
    }
    return counts;
  }, [threads]);

  const filteredThreads = useMemo(() => {
    return threads.filter((thread) => {
      const matchesSearch =
        !searchQuery ||
        thread.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        thread.repository.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesStatus =
        statusFilter === "all" || thread.status === statusFilter;

      return matchesSearch && matchesStatus;
    });
  }, [threads, searchQuery, statusFilter]);

  const groupedThreads = useMemo(() => {
    return {
      running: filteredThreads.filter((t) => t.status === "running"),
      committing: filteredThreads.filter((t) => t.status === "committing"),
      pending: filteredThreads.filter((t) => t.status === "pending"),
      complete: filteredThreads.filter((t) => t.status === "complete"),
      failed: filteredThreads.filter((t) => t.status === "failed"),
      cancelled: filteredThreads.filter((t) => t.status === "cancelled"),
    };
  }, [filteredThreads]);

  const showLoading = isLoading && threads.length === 0;
  const showEmpty = !isLoading && filteredThreads.length === 0;

  return (
    <div className="bg-background flex h-screen flex-col">
      <AppHeader showBrand>
        <Link
          href="/chat"
          className="border-border inline-flex h-8 items-center gap-1.5 rounded-md border bg-transparent px-3 text-xs transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          <Plus className="h-3.5 w-3.5" />
          New Task
        </Link>
        <span className="text-muted-foreground text-xs">
          {filteredThreads.length} thread{filteredThreads.length !== 1 ? "s" : ""}
        </span>
      </AppHeader>

      {/* Search and Filters */}
      <div className="border-border bg-muted/50 border-b px-4 py-3">
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative max-w-md flex-1">
            <Search className="text-muted-foreground absolute top-1/2 left-3 h-4 w-4 -translate-y-1/2" />
            <Input
              placeholder="Search threads..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="border-border bg-background text-foreground placeholder:text-muted-foreground pl-10"
            />
          </div>
          <div className="flex items-center gap-1">
            <Filter className="text-muted-foreground mr-1.5 h-4 w-4" />
            {FILTER_STATUSES.map((status) => (
              <Button
                key={status}
                variant={statusFilter === status ? "secondary" : "ghost"}
                size="sm"
                className={cn(
                  "h-7 text-xs",
                  statusFilter === status
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground",
                )}
                onClick={() => setStatusFilter(status)}
              >
                {status === "all"
                  ? "All"
                  : status.charAt(0).toUpperCase() + status.slice(1)}
                <Badge
                  variant="secondary"
                  className="bg-muted/70 text-muted-foreground ml-1 text-xs"
                >
                  {statusCounts[status]}
                </Badge>
              </Button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-6xl p-4">
          {showLoading && (
            <div>
              <div className="mb-3 flex items-center gap-2">
                <h2 className="text-foreground text-base font-semibold">
                  Loading threads...
                </h2>
              </div>
              <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                {Array.from({ length: 9 }).map((_, i) => (
                  <ThreadCardLoading key={`loading-${i}`} />
                ))}
              </div>
            </div>
          )}

          {!showLoading && statusFilter === "all" && (
            <div className="space-y-6">
              {Object.entries(groupedThreads).map(([status, group]) => {
                if (group.length === 0) return null;
                return (
                  <div key={status}>
                    <div className="mb-3 flex items-center gap-2">
                      <h2 className="text-foreground text-base font-semibold capitalize">
                        {status} Threads
                      </h2>
                      <Badge
                        variant="secondary"
                        className="bg-muted/70 text-muted-foreground text-xs"
                      >
                        {group.length}
                      </Badge>
                    </div>
                    <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
                      {group.map((thread) => (
                        <ThreadCard key={thread.id} thread={thread} />
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {!showLoading && statusFilter !== "all" && (
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3">
              {filteredThreads.map((thread) => (
                <ThreadCard key={thread.id} thread={thread} />
              ))}
            </div>
          )}

          {showEmpty && (
            <div className="py-12 text-center">
              <div className="text-muted-foreground mb-2">
                No threads found
              </div>
              <div className="text-muted-foreground/70 text-xs">
                {threads.length === 0
                  ? "No threads have been created yet"
                  : searchQuery
                    ? "Try adjusting your search query"
                    : "No threads match the selected filter"}
              </div>
              {threads.length === 0 && (
                <Link
                  href="/chat"
                  className="border-border mt-4 inline-flex items-center rounded-md border bg-transparent px-3 py-1.5 text-sm transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <Plus className="mr-1.5 h-3.5 w-3.5" />
                  Create your first task
                </Link>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
