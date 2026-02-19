import { cn } from "@/lib/utils";

interface ChatMessageProps {
  role: "user" | "assistant" | "system";
  parts: Array<{ type: string; text?: string }>;
}

export function ChatMessage({ role, parts }: ChatMessageProps) {
  const text = parts
    .filter((p) => p.type === "text")
    .map((p) => p.text ?? "")
    .join("");

  if (!text) return null;

  return (
    <div
      className={cn(
        "flex gap-[var(--space-3)] px-[var(--space-4)] py-[var(--space-3)]",
        role === "user" ? "justify-end" : "justify-start",
      )}
    >
      <div
        className={cn(
          "max-w-[80%] rounded-[var(--radius-lg)] px-[var(--space-4)] py-[var(--space-3)]",
          role === "user"
            ? "bg-[var(--color-accent)] text-[var(--color-text-inverse)]"
            : "bg-[var(--color-bg-secondary)] text-[var(--color-text)]",
        )}
      >
        <div className="whitespace-pre-wrap text-[var(--text-sm)] leading-relaxed">
          {text}
        </div>
      </div>
    </div>
  );
}
