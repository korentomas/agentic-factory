"use client";

import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { StickToBottom } from "use-stick-to-bottom";
import { StickyToBottomContent, ScrollToBottom } from "@/utils/scroll-utils";
import { ManagerChat } from "./manager-chat";
import { ActionsRenderer } from "./actions-renderer";
import { CancelStreamButton } from "./cancel-stream-button";
import { TokenUsage } from "./token-usage";
import { ThreadViewLoading } from "./thread-view-loading";
import { AppHeader } from "./app-header";
import { cn } from "@/lib/utils";
import { useTaskStream } from "@/hooks/use-task-stream";
import type { ThreadStatus } from "./types";

interface ThreadViewProps {
  threadId: string;
}

function getStatusDotColor(status: ThreadStatus | string): string {
  switch (status) {
    case "running":
    case "committing":
      return "bg-blue-500 dark:bg-blue-400";
    case "complete":
      return "bg-green-500 dark:bg-green-400";
    case "pending":
      return "bg-gray-500 dark:bg-gray-400";
    case "failed":
      return "bg-red-500 dark:bg-red-400";
    case "cancelled":
      return "bg-yellow-500 dark:bg-yellow-400";
    default:
      return "bg-gray-500 dark:bg-gray-400";
  }
}

function getStatusLabel(status: ThreadStatus | string): string {
  switch (status) {
    case "running":
      return "Running";
    case "committing":
      return "Committing";
    case "complete":
      return "Complete";
    case "pending":
      return "Pending";
    case "failed":
      return "Failed";
    case "cancelled":
      return "Cancelled";
    default:
      return status;
  }
}

export function ThreadView({ threadId }: ThreadViewProps) {
  const router = useRouter();
  const { messages, threadStatus, isConnected, isComplete } =
    useTaskStream(threadId);

  const status = (threadStatus?.status ?? "pending") as ThreadStatus;
  const isStreaming =
    status === "running" || status === "committing" || status === "pending";
  const title = threadStatus?.title ?? "Untitled task";

  if (!isConnected && messages.length === 0) {
    return <ThreadViewLoading onBackToHome={() => router.push("/chat")} />;
  }

  // Adapt SSE messages to TaskMessage shape for child components
  const taskMessages = messages.map((m) => ({
    id: m.id,
    threadId,
    role: m.role as "human" | "assistant" | "tool" | "system" | "manager",
    content: m.content ?? "",
    toolName: m.toolName,
    toolInput: m.toolInput,
    toolOutput: m.toolOutput,
    createdAt: new Date(m.createdAt),
  }));

  return (
    <div className="bg-background flex h-screen flex-1 flex-col">
      <AppHeader
        showBackButton
        backHref="/chat"
        className="absolute top-0 right-0 left-0 z-10"
        titleContent={
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <div
              className={cn(
                "size-2 flex-shrink-0 rounded-full",
                getStatusDotColor(status),
                isStreaming && "animate-pulse",
              )}
            />
            <span className="text-muted-foreground max-w-[500px] truncate font-mono text-sm">
              {title}
            </span>
            <span className="text-muted-foreground text-xs">
              {getStatusLabel(status)}
            </span>
          </div>
        }
      >
        {isStreaming && (
          <CancelStreamButton threadId={threadId} isRunning={isStreaming} />
        )}
        <TokenUsage
          costUsd={threadStatus?.costUsd}
          durationMs={threadStatus?.durationMs}
          engine={threadStatus?.engine}
          model={threadStatus?.model}
          numTurns={threadStatus?.numTurns}
        />
      </AppHeader>

      {/* Main Content — Split Layout */}
      <div className="flex w-full pt-12" style={{ height: "calc(100vh)" }}>
        {/* Left: Manager Chat (1/3) */}
        <ManagerChat
          messages={taskMessages}
          threadId={threadId}
          threadStatus={status}
          isStreaming={isStreaming}
        />

        {/* Right: Actions Pane (2/3) */}
        <div
          className="flex flex-1 flex-col px-4 pt-4"
          style={{ height: "calc(100vh - 3rem)" }}
        >
          <Card className="border-border bg-card relative h-full p-0">
            <CardContent className="h-full p-0">
              <StickToBottom className="absolute inset-0 h-full" initial={true}>
                <StickyToBottomContent
                  className="scrollbar-pretty-auto h-full"
                  content={
                    <div className="overflow-y-auto px-2">
                      <ActionsRenderer
                        messages={taskMessages}
                        threadStatus={status}
                        isStreaming={isStreaming}
                      />
                    </div>
                  }
                  footer={
                    <div className="absolute right-0 bottom-4 left-0 flex w-full justify-center">
                      <ScrollToBottom className="animate-in fade-in-0 zoom-in-95" />
                    </div>
                  }
                />
              </StickToBottom>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
