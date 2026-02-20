"use client";

import { useState } from "react";
import { StickToBottom } from "use-stick-to-bottom";
import { StickyToBottomContent, ScrollToBottom } from "@/utils/scroll-utils";
import { TooltipIconButton } from "@/components/ui/tooltip-icon-button";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import {
  ArrowUp,
  Bot,
  Copy,
  CopyCheck,
  Loader2,
  User,
  Wrench,
  AlertCircle,
} from "lucide-react";
import dynamic from "next/dynamic";
import { cn } from "@/lib/utils";

const MarkdownContent = dynamic(
  () => import("./markdown-content").then((mod) => mod.MarkdownContent),
  { loading: () => <span className="text-muted-foreground text-sm">...</span> },
);
import type { TaskMessage, ThreadStatus } from "./types";

function MessageCopyButton({ content }: { content: string }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent<HTMLButtonElement>) => {
    e.stopPropagation();
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <TooltipIconButton
      onClick={handleCopy}
      variant="ghost"
      tooltip="Copy content"
      className="size-6 p-1"
    >
      {copied ? (
        <CopyCheck className="h-3 w-3 text-green-500" />
      ) : (
        <Copy className="h-3 w-3" />
      )}
    </TooltipIconButton>
  );
}

function LoadingDots() {
  return (
    <div className="flex items-center space-x-1 text-sm">
      {[0, 200, 400].map((delay) => (
        <div
          key={delay}
          className="bg-muted-foreground h-1 w-1 animate-bounce rounded-full"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </div>
  );
}

function getRoleIcon(role: string) {
  switch (role) {
    case "human":
      return (
        <div className="bg-muted flex h-6 w-6 items-center justify-center rounded-full">
          <User className="text-muted-foreground h-4 w-4" />
        </div>
      );
    case "assistant":
    case "manager":
      return (
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-950/50">
          <Bot className="h-4 w-4 text-blue-700 dark:text-blue-300" />
        </div>
      );
    case "tool":
      return (
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-orange-100 dark:bg-orange-950/50">
          <Wrench className="h-4 w-4 text-orange-700 dark:text-orange-300" />
        </div>
      );
    default:
      return (
        <div className="bg-muted flex h-6 w-6 items-center justify-center rounded-full">
          <Bot className="text-muted-foreground h-4 w-4" />
        </div>
      );
  }
}

function getRoleLabel(role: string): string {
  switch (role) {
    case "human":
      return "You";
    case "assistant":
      return "LailaTov";
    case "manager":
      return "Manager";
    case "tool":
      return "Tool";
    case "system":
      return "System";
    default:
      return role;
  }
}

interface ManagerChatProps {
  messages: TaskMessage[];
  threadId: string;
  threadStatus: ThreadStatus;
  isStreaming: boolean;
}

export function ManagerChat({
  messages,
  threadId,
  threadStatus,
  isStreaming,
}: ManagerChatProps) {
  const [chatInput, setChatInput] = useState("");
  const [sending, setSending] = useState(false);

  // Only show human, manager, and system messages in the chat pane (tool steps go to actions pane)
  const chatMessages = messages.filter(
    (m) => m.role === "human" || m.role === "manager" || m.role === "system",
  );

  const canSend =
    chatInput.trim().length > 0 &&
    !sending &&
    threadStatus !== "complete" &&
    threadStatus !== "failed" &&
    threadStatus !== "cancelled";

  const handleSend = async () => {
    if (!canSend) return;
    const content = chatInput.trim();
    setChatInput("");
    setSending(true);
    try {
      await fetch(`/api/tasks/${threadId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
    } catch {
      // Message send failed — user can retry
    } finally {
      setSending(false);
    }
  };

  const isTerminal =
    threadStatus === "complete" ||
    threadStatus === "failed" ||
    threadStatus === "cancelled";

  return (
    <div className="border-border bg-muted/30 flex h-full w-1/3 flex-col overflow-hidden border-r">
      <div className="relative flex-1">
        <StickToBottom className="absolute inset-0" initial={true}>
          <StickyToBottomContent
            className="scrollbar-pretty-auto h-full"
            contentClassName="space-y-4 p-4"
            content={
              <>
                {chatMessages.map((message) => (
                  <div
                    key={message.id}
                    className="group flex items-start gap-3 rounded-lg bg-muted p-3"
                  >
                    <div className="mt-0.5 flex-shrink-0">
                      {getRoleIcon(message.role)}
                    </div>
                    <div className="relative min-w-0 flex-1 space-y-1 overflow-x-hidden">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-muted-foreground text-xs font-medium">
                          {getRoleLabel(message.role)}
                        </span>
                        <div className="opacity-0 transition-opacity group-hover:opacity-100">
                          <MessageCopyButton content={message.content} />
                        </div>
                      </div>
                      {message.content ? (
                        <div className="prose prose-sm dark:prose-invert max-w-none text-sm">
                          <MarkdownContent content={message.content} />
                        </div>
                      ) : (
                        <LoadingDots />
                      )}
                    </div>
                  </div>
                ))}
                {isStreaming && chatMessages.length === 0 && (
                  <div className="flex items-start gap-3 rounded-lg bg-muted p-3">
                    <div className="mt-0.5 flex-shrink-0">
                      {getRoleIcon("assistant")}
                    </div>
                    <div className="min-w-0 flex-1">
                      <span className="text-muted-foreground text-xs font-medium">
                        LailaTov
                      </span>
                      <LoadingDots />
                    </div>
                  </div>
                )}
                {threadStatus === "failed" && (
                  <div className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 dark:border-red-900 dark:bg-red-950/30">
                    <AlertCircle className="h-4 w-4 text-red-500" />
                    <span className="text-sm text-red-700 dark:text-red-400">
                      Task execution failed
                    </span>
                  </div>
                )}
              </>
            }
            footer={
              <div className="absolute right-0 bottom-4 left-0 flex w-full justify-center">
                <ScrollToBottom className="animate-in fade-in-0 zoom-in-95" />
              </div>
            }
          />
        </StickToBottom>
      </div>

      <div className="border-border bg-muted/30 border-t p-4">
        {isTerminal ? (
          <div className="flex items-center justify-center py-2">
            <Badge
              variant="outline"
              className={cn(
                "text-xs",
                threadStatus === "complete" && "border-green-200 text-green-600 dark:border-green-800 dark:text-green-400",
                threadStatus === "failed" && "border-red-200 text-red-600 dark:border-red-800 dark:text-red-400",
                threadStatus === "cancelled" && "border-yellow-200 text-yellow-600 dark:border-yellow-800 dark:text-yellow-400",
              )}
            >
              Task {threadStatus}
            </Badge>
          </div>
        ) : (
          <>
            <div className="flex gap-2">
              <Textarea
                value={chatInput}
                onChange={(e) => setChatInput(e.target.value)}
                placeholder="Guide the agent..."
                className="border-border bg-background text-foreground placeholder:text-muted-foreground min-h-[60px] flex-1 resize-none text-sm"
                onKeyDown={(e) => {
                  if (
                    e.key === "Enter" &&
                    (e.metaKey || e.ctrlKey) &&
                    canSend
                  ) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
              />
              {sending || isStreaming ? (
                <TooltipIconButton
                  className="size-8 self-end rounded-full"
                  variant="secondary"
                  tooltip="Agent is working"
                  disabled
                >
                  <Loader2 className="size-4 animate-spin" />
                </TooltipIconButton>
              ) : (
                <Button
                  onClick={handleSend}
                  disabled={!canSend}
                  size="icon"
                  variant="default"
                  className="size-8 self-end rounded-full"
                >
                  <ArrowUp className="size-4" />
                </Button>
              )}
            </div>
            <div className="text-muted-foreground mt-2 text-xs">
              Press Cmd+Enter to send
            </div>
          </>
        )}
      </div>
    </div>
  );
}
