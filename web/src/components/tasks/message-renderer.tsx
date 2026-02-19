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
    bg: "bg-[var(--color-accent)]/10",
    avatarBg: "bg-[var(--color-accent)]",
  },
  assistant: {
    icon: Bot,
    label: "Agent",
    align: "left",
    bg: "bg-[var(--color-bg-secondary)]",
    avatarBg: "bg-[var(--color-bg-elevated)]",
  },
  tool: {
    icon: Terminal,
    label: "Tool",
    align: "left",
    bg: "bg-[var(--color-bg-surface)]",
    avatarBg: "bg-[var(--color-bg-warm)]",
  },
  system: {
    icon: Info,
    label: "System",
    align: "left",
    bg: "bg-[var(--color-bg-warm)]",
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
    <div className="overflow-hidden rounded-[var(--radius-md)] border border-[var(--color-border)]">
      <button
        type="button"
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center gap-[var(--space-2)] bg-[var(--color-bg-secondary)] px-[var(--space-3)] py-[var(--space-2)] text-left transition-colors hover:bg-[var(--color-bg-elevated)]"
      >
        {expanded ? (
          <ChevronDown className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
        ) : (
          <ChevronRight className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
        )}
        <Terminal className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
        <span className="font-mono text-[var(--text-xs)] font-medium text-[var(--color-text)]">
          {toolName}
        </span>
      </button>

      {expanded && (
        <div className="border-t border-[var(--color-border)]">
          {toolInput && (
            <div className="border-b border-[var(--color-border)] px-[var(--space-3)] py-[var(--space-2)]">
              <p className="mb-[var(--space-1)] text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
                Input
              </p>
              <pre className="whitespace-pre-wrap font-mono text-[var(--text-xs)] text-[var(--color-text-secondary)]">
                {toolInput}
              </pre>
            </div>
          )}
          {toolOutput && (
            <div className="px-[var(--space-3)] py-[var(--space-2)]">
              <p className="mb-[var(--space-1)] text-[10px] font-medium uppercase tracking-wider text-[var(--color-text-muted)]">
                Output
              </p>
              <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-[var(--text-xs)] text-[var(--color-text-secondary)]">
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
        "flex gap-[var(--space-3)] px-[var(--space-4)] py-[var(--space-3)]",
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
              ? "text-[var(--color-text-inverse)]"
              : "text-[var(--color-text-secondary)]",
          )}
        />
      </div>

      {/* Content */}
      <div
        className={cn(
          "max-w-[80%] rounded-[var(--radius-lg)] px-[var(--space-4)] py-[var(--space-3)]",
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
          <div className="whitespace-pre-wrap text-[var(--text-sm)] leading-relaxed text-[var(--color-text)]">
            {content}
          </div>
        )}

        <p
          className={cn(
            "mt-[var(--space-1)] text-[10px] text-[var(--color-text-muted)]",
            config.align === "right" ? "text-right" : "text-left",
          )}
        >
          {formatTime(createdAt)}
        </p>
      </div>
    </div>
  );
}
