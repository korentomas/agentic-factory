"use client";

import { useChat } from "@ai-sdk/react";
import { useRef, useEffect, useState, useCallback } from "react";
import { Send } from "lucide-react";
import { ChatMessage } from "./chat-message";

export function ChatPanel() {
  const scrollRef = useRef<HTMLDivElement>(null);
  const [input, setInput] = useState("");

  const { messages, sendMessage, status } = useChat();

  const isLoading = status === "submitted" || status === "streaming";

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const text = input.trim();
      if (!text || isLoading) return;
      setInput("");
      await sendMessage({ text });
    },
    [input, isLoading, sendMessage],
  );

  return (
    <div className="flex h-[600px] flex-col rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)]">
      {/* Messages */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto py-[var(--space-4)]"
      >
        {messages.length === 0 && (
          <div className="flex h-full items-center justify-center">
            <div className="text-center">
              <p className="text-[var(--text-lg)] font-medium text-[var(--color-text-muted)]">
                Talk to your codebase
              </p>
              <p className="mt-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text-muted)]">
                Ask questions, review code, or type /task to dispatch work
              </p>
            </div>
          </div>
        )}
        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            role={msg.role as "user" | "assistant"}
            parts={msg.parts as Array<{ type: string; text?: string }>}
          />
        ))}
        {isLoading && (
          <div className="px-[var(--space-4)] py-[var(--space-3)]">
            <div className="flex gap-1">
              <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--color-text-muted)]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--color-text-muted)] [animation-delay:0.1s]" />
              <span className="h-2 w-2 animate-bounce rounded-full bg-[var(--color-text-muted)] [animation-delay:0.2s]" />
            </div>
          </div>
        )}
      </div>

      {/* Input */}
      <form
        onSubmit={handleSubmit}
        className="border-t border-[var(--color-border)] p-[var(--space-4)]"
      >
        <div className="flex gap-[var(--space-2)]">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about your code, or /task to dispatch..."
            className="flex-1 rounded-[var(--radius-md)] border border-[var(--color-border)] bg-[var(--color-bg)] px-[var(--space-4)] py-[var(--space-3)] text-[var(--text-sm)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            aria-label="Send"
            className="rounded-[var(--radius-md)] bg-[var(--color-accent)] p-[var(--space-3)] text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
          </button>
        </div>
        <p className="mt-[var(--space-2)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
          /task to create work &middot; /explain to understand code
        </p>
      </form>
    </div>
  );
}
