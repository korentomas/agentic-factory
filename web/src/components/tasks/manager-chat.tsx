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
    <div className="flex h-full flex-col rounded-lg border border-border bg-card">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <MessageSquare className="h-4 w-4 text-[var(--color-info)]" />
        <div>
          <p className="text-sm font-medium text-foreground">
            Manager
          </p>
          <p className="text-xs text-muted-foreground">
            Guide the agent
          </p>
        </div>
      </div>

      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto px-4 py-3"
      >
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <MessageSquare className="mx-auto h-8 w-8 text-muted-foreground/40" />
              <p className="mt-2 text-sm text-muted-foreground">
                No messages yet
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                Send a message to interrupt or guide the running agent
              </p>
            </div>
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "mb-3 flex",
              msg.sender === "user" ? "justify-end" : "justify-start",
            )}
          >
            <div
              className={cn(
                "max-w-[85%] rounded-lg px-3 py-2",
                msg.sender === "user"
                  ? "bg-[var(--color-info)]/10 text-foreground"
                  : "bg-muted text-foreground",
              )}
            >
              <p className="whitespace-pre-wrap text-sm leading-relaxed">
                {msg.content}
              </p>
              <p className="mt-1 text-[10px] text-muted-foreground">
                {formatTime(msg.createdAt)}
              </p>
            </div>
          </div>
        ))}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-border p-3"
      >
        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={disabled}
            placeholder={
              disabled
                ? "Task is not running"
                : "Send a message to the agent..."
            }
            className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!input.trim() || disabled}
            aria-label="Send message"
            className="rounded-md bg-primary p-2 text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
      </form>
    </div>
  );
}
