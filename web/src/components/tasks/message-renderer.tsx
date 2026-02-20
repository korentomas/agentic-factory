"use client";

import { useState } from "react";
import {
  User,
  Bot,
  Terminal,
  Info,
  MessageSquare,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface TaskMessageProps {
  role: string;
  content: string | null;
  toolName?: string | null;
  toolInput?: string | null;
  toolOutput?: string | null;
  createdAt: Date | string;
}

const ROLE_CONFIG: Record<
  string,
  {
    icon: typeof User;
    label: string;
    align: "left" | "right";
    bg: string;
    avatarBg: string;
  }
> = {
  human: {
    icon: User,
    label: "You",
    align: "right",
    bg: "bg-primary/10",
    avatarBg: "bg-primary",
  },
  assistant: {
    icon: Bot,
    label: "Agent",
    align: "left",
    bg: "bg-muted",
    avatarBg: "bg-card",
  },
  tool: {
    icon: Terminal,
    label: "Tool",
    align: "left",
    bg: "bg-card",
    avatarBg: "bg-secondary",
  },
  system: {
    icon: Info,
    label: "System",
    align: "left",
    bg: "bg-secondary",
    avatarBg: "bg-[var(--color-warning)]/20",
  },
  manager: {
    icon: MessageSquare,
    label: "Manager",
    align: "left",
    bg: "bg-[var(--color-info)]/10",
    avatarBg: "bg-[var(--color-info)]/20",
  },
};

function formatTime(date: Date | string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return d.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ToolCallContent({
  toolName,
  toolInput,
  toolOutput,
}: {
  toolName: string;
  toolInput: string | null;
  toolOutput: string | null;
}) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="overflow-hidden rounded-md border border-border">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-2 bg-muted px-3 py-2 text-left transition-colors hover:bg-card"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
        )}
        <Terminal className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="font-mono text-xs font-medium text-foreground">
          {toolName}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-border">
          {toolInput && (
            <div className="border-b border-border px-3 py-2">
              <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Input
              </p>
              <pre className="whitespace-pre-wrap font-mono text-xs text-muted-foreground">
                {toolInput}
              </pre>
            </div>
          )}
          {toolOutput && (
            <div className="px-3 py-2">
              <p className="mb-1 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                Output
              </p>
              <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-xs text-muted-foreground">
                {toolOutput}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function MessageRenderer({
  role,
  content,
  toolName,
  toolInput,
  toolOutput,
  createdAt,
}: TaskMessageProps) {
  const config = ROLE_CONFIG[role] ?? ROLE_CONFIG.assistant;
  const RoleIcon = config.icon;

  const isToolCall = role === "tool" && toolName;

  if (!content && !isToolCall) return null;

  return (
    <div
      className={cn(
        "flex gap-3 px-4 py-3",
        config.align === "right" ? "flex-row-reverse" : "flex-row",
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          config.avatarBg,
        )}
      >
        <RoleIcon
          className={cn(
            "h-3.5 w-3.5",
            role === "human"
              ? "text-primary-foreground"
              : "text-muted-foreground",
          )}
        />
      </div>

      {/* Content */}
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-4 py-3",
          config.bg,
        )}
      >
        {isToolCall ? (
          <ToolCallContent
            toolName={toolName}
            toolInput={toolInput ?? null}
            toolOutput={toolOutput ?? null}
          />
        ) : (
          <div className="whitespace-pre-wrap text-sm leading-relaxed text-foreground">
            {content}
          </div>
        )}

        <p
          className={cn(
            "mt-1 text-[10px] text-muted-foreground",
            config.align === "right" ? "text-right" : "text-left",
          )}
        >
          {formatTime(createdAt)}
        </p>
      </div>
    </div>
  );
}
