"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { MessageSquare, Send } from "lucide-react";
import { cn } from "@/lib/utils";

interface ManagerChatProps {
  threadId: string;
  messages: Array<{
    id: string;
    content: string;
    sender: "user" | "system";
    createdAt: Date;
  }>;
  disabled?: boolean;
  onSend: (content: string) => void;
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function ManagerChat({
  threadId,
  messages,
  disabled,
  onSend,
}: ManagerChatProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      const text = input.trim();
      if (!text || disabled) return;
      setInput("");
      onSend(text);
    },
    [input, disabled, onSend],
  );

  return (
    <div className="flex h-full flex-col rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)]">
      {/* Header */}
      <div className="flex items-center gap-[var(--space-2)] border-b border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-3)]">
        <MessageSquare className="h-4 w-4 text-[var(--color-info)]" />
        <div>
          <p className="text-[var(--text-sm)] font-medium text-[var(--color-text)]">
            Manager
          </p>
          <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
            Guide the agent
          </p>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-[var(--space-4)] py-[var(--space-3)]"
      >
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <MessageSquare className="mx-auto h-8 w-8 text-[var(--color-text-muted)]/40" />
              <p className="mt-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text-muted)]">
                No messages yet
              </p>
              <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
                Send a message to interrupt or guide the running agent
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "mb-[var(--space-3)] flex",
              msg.sender === "user" ? "justify-end" : "justify-start",
            )}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-[var(--radius-lg)] px-[var(--space-3)] py-[var(--space-2)]",
                msg.sender === "user"
                  ? "bg-[var(--color-info)]/10 text-[var(--color-text)]"
                  : "bg-[var(--color-bg-secondary)] text-[var(--color-text)]",
              )}
            >
              <p className="whitespace-pre-wrap text-[var(--text-sm)] leading-relaxed">
                {msg.content}
              </p>
              <p className="mt-[var(--space-1)] text-[10px] text-[var(--color-text-muted)]">
                {formatTime(msg.createdAt)}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-[var(--color-border)] p-[var(--space-3)]"
      >
        <div className="flex gap-[var(--space-2)]">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={disabled}
            placeholder={
              disabled
                ? "Task is not running"
                : "Send a message to the agent..."
            }
            className="flex-1 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg)] px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            aria-label="Send message"
            className="rounded-[var(--radius-md)] bg-[var(--color-accent)] p-[var(--space-2)] text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
