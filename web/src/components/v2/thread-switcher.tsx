"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { Layers3, Plus } from "lucide-react";
import { useRouter } from "next/navigation";
import type { ThreadMetadata, ThreadStatus } from "./types";
import { ThreadCard } from "./thread-card";

interface TaskThreadRow {
  id: string;
  repoUrl: string;
  branch: string;
  baseBranch: string;
  title: string;
  description: string;
  status: ThreadStatus;
  engine: string | null;
  model: string | null;
  costUsd: string | null;
  durationMs: number | null;
  createdAt: string;
  updatedAt: string;
}

function toThreadMetadata(row: TaskThreadRow): ThreadMetadata {
  return {
    id: row.id,
    title: row.title,
    repository: row.repoUrl,
    branch: row.branch,
    baseBranch: row.baseBranch,
    status: row.status,
    engine: row.engine,
    model: row.model,
    costUsd: row.costUsd ? Number(row.costUsd) : 0,
    durationMs: row.durationMs ?? 0,
    lastActivity: new Date(row.updatedAt),
    createdAt: new Date(row.createdAt),
  };
}

interface ThreadSwitcherProps {
  currentThreadId: string;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export function ThreadSwitcher({ currentThreadId }: ThreadSwitcherProps) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  const { data, isLoading } = useSWR<{ threads: TaskThreadRow[] }>(
    open ? "/api/tasks" : null,
    fetcher,
  );

  const threads = useMemo(
    () => (data?.threads ?? []).map(toThreadMetadata),
    [data],
  );
  const currentThread = threads.find((t) => t.id === currentThreadId);
  const otherThreads = threads.filter((t) => t.id !== currentThreadId);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button
          variant="outline"
          size="sm"
          className="border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground h-7 gap-1 text-xs"
        >
          <Layers3 className="h-3 w-3" />
          <span className="hidden sm:inline">Switch Thread</span>
        </Button>
      </SheetTrigger>
      <SheetContent
        side="right"
        className="border-border bg-background w-80 sm:w-96"
      >
        <SheetHeader className="pb-4">
          <SheetTitle className="text-foreground text-base">
            All Threads
          </SheetTitle>
        </SheetHeader>

        <div className="mx-2 h-full space-y-3">
          {/* New Chat Button */}
          <Button
            onClick={() => {
              router.push("/chat");
              setOpen(false);
            }}
            className="border-border bg-card text-foreground hover:bg-muted h-8 w-full justify-start gap-2 text-xs"
            variant="outline"
          >
            <Plus className="h-3 w-3" />
            Start New Task
          </Button>

          {/* Current Thread */}
          {currentThread && (
            <div className="space-y-2">
              <h3 className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                Current Thread
              </h3>
              <ThreadCard thread={currentThread} />
            </div>
          )}

          {/* Other Threads */}
          <div className="space-y-2">
            <h3 className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
              Other Threads
            </h3>
            {isLoading ? (
              <ScrollArea className="h-[calc(100vh-280px)]">
                <div className="space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className="border-border space-y-2 rounded-lg border p-3"
                    >
                      <Skeleton className="h-4 w-3/4" />
                      <Skeleton className="h-3 w-1/2" />
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : otherThreads.length > 0 ? (
              <ScrollArea className="h-[calc(100vh-280px)]">
                <div className="space-y-2">
                  {otherThreads.map((thread) => (
                    <div
                      key={thread.id}
                      onClick={() => {
                        router.push(`/chat/${thread.id}`);
                        setOpen(false);
                      }}
                    >
                      <ThreadCard thread={thread} />
                    </div>
                  ))}
                </div>
              </ScrollArea>
            ) : (
              <div className="flex h-32 items-center justify-center">
                <p className="text-muted-foreground text-sm">
                  No other threads
                </p>
              </div>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
