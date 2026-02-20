"use client";

import { useState, useMemo } from "react";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { Archive, Settings, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ThreadCard, ThreadCardLoading } from "./thread-card";
import { TerminalInput } from "./terminal-input";
import { QuickActions } from "./quick-actions";
import { GitHubInstallationBanner } from "../github/installation-banner";
import { AppHeader } from "./app-header";
import { Toaster } from "sonner";
import { toThreadMetadata, fetcher } from "./thread-data";
import type { TaskThreadRow } from "./thread-data";
import NextLink from "next/link";

function OpenSettingsButton() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          asChild
          className="hover:bg-accent hover:text-accent-foreground size-6 rounded-md p-1 hover:cursor-pointer"
        >
          <NextLink href="/chat/settings">
            <Settings className="size-4" />
          </NextLink>
        </TooltipTrigger>
        <TooltipContent side="bottom">Settings</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function OpenDocumentationButton() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          asChild
          className="hover:bg-accent hover:text-accent-foreground size-6 rounded-md p-1 hover:cursor-pointer"
        >
          <a
            href="https://github.com/korentomas/agentic-factory"
            target="_blank"
            rel="noopener noreferrer"
          >
            <BookOpen className="size-4" />
          </a>
        </TooltipTrigger>
        <TooltipContent side="bottom">Documentation</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

interface DefaultViewProps {
  hasRepos: boolean;
}

export function DefaultView({ hasRepos }: DefaultViewProps) {
  const router = useRouter();
  const [quickActionPrompt, setQuickActionPrompt] = useState("");

  const { data, isLoading } = useSWR<{ threads: TaskThreadRow[] }>(
    "/api/tasks",
    fetcher,
    { refreshInterval: 10_000 },
  );

  const threads = useMemo(
    () => (data?.threads ?? []).map(toThreadMetadata),
    [data],
  );

  const displayThreads = threads.slice(0, 4);
  const threadsLoading = isLoading && threads.length === 0;

  return (
    <div className="flex flex-1 flex-col">
      <Toaster />

      <AppHeader showBrand>
        <div className="flex items-center gap-2">
          <span className="text-muted-foreground text-xs">ready</span>
          <div className="h-1.5 w-1.5 rounded-full bg-green-500 dark:bg-green-600" />
        </div>
        <OpenDocumentationButton />
        <OpenSettingsButton />
      </AppHeader>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-6 p-4">
          <GitHubInstallationBanner hasRepos={hasRepos} />

          {/* Terminal Input — hero element */}
          <div className="pt-8">
            <TerminalInput
              placeholder="Describe your coding task or ask a question..."
              quickActionPrompt={quickActionPrompt}
              setQuickActionPrompt={setQuickActionPrompt}
            />
          </div>

          {/* Recent & Running Threads */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-foreground text-base font-semibold">
                Recent & Running Threads
              </h2>
              <Button
                variant="outline"
                size="sm"
                className="border-border text-muted-foreground hover:text-foreground h-7 text-xs"
                onClick={() => router.push("/chat/threads")}
              >
                View All
              </Button>
            </div>

            {threadsLoading || threads.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2">
                {threadsLoading && (
                  <>
                    <ThreadCardLoading />
                    <ThreadCardLoading />
                    <ThreadCardLoading />
                    <ThreadCardLoading />
                  </>
                )}
                {displayThreads.map((thread) => (
                  <ThreadCard key={thread.id} thread={thread} />
                ))}
              </div>
            ) : (
              <div className="flex items-center justify-center py-8">
                <span className="text-muted-foreground flex items-center gap-2">
                  <Archive className="size-4" />
                  <span className="text-sm">No threads yet</span>
                </span>
              </div>
            )}
          </div>

          <QuickActions setQuickActionPrompt={setQuickActionPrompt} />
        </div>
      </div>
    </div>
  );
}
