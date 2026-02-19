"use client";

import { useState, useCallback, useRef } from "react";
import { Terminal, GitBranch, Send } from "lucide-react";
import { cn } from "@/lib/utils";

interface TerminalInputProps {
  repos: Array<{ fullName: string; url: string }>;
  onSubmit: (task: {
    repoUrl: string;
    branch: string;
    title: string;
    description: string;
  }) => void;
  disabled?: boolean;
}

export function TerminalInput({ repos, onSubmit, disabled }: TerminalInputProps) {
  const [selectedRepo, setSelectedRepo] = useState(repos[0]?.url ?? "");
  const [branch, setBranch] = useState("main");
  const [description, setDescription] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const text = description.trim();
    if (!text || !selectedRepo || disabled) return;

    const firstLine = text.split("\n")[0] ?? text;
    onSubmit({
      repoUrl: selectedRepo,
      branch,
      title: firstLine.slice(0, 120),
      description: text,
    });
    setDescription("");
  }, [description, selectedRepo, branch, disabled, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const selectedRepoName =
    repos.find((r) => r.url === selectedRepo)?.fullName ?? "Select repo";

  return (
    <div
      className={cn(
        "overflow-hidden rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] shadow-[var(--shadow-sm)]",
        disabled && "opacity-60",
      )}
    >
      {/* Top bar */}
      <div className="flex items-center gap-[var(--space-2)] border-b border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-3)]">
        <Terminal className="h-4 w-4 text-[var(--color-text-muted)]" />

        <select
          value={selectedRepo}
          onChange={(e) => setSelectedRepo(e.target.value)}
          disabled={disabled}
          className="rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-[var(--space-2)] py-[var(--space-1)] font-mono text-[var(--text-xs)] text-[var(--color-text)] focus:border-[var(--color-accent)] focus:outline-none"
        >
          {repos.map((repo) => (
            <option key={repo.url} value={repo.url}>
              {repo.fullName}
            </option>
          ))}
        </select>

        <span className="text-[var(--color-text-muted)]">/</span>

        <GitBranch className="h-3.5 w-3.5 text-[var(--color-text-muted)]" />
        <input
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          disabled={disabled}
          placeholder="main"
          className="w-28 rounded-[var(--radius-sm)] border border-[var(--color-border)] bg-[var(--color-bg)] px-[var(--space-2)] py-[var(--space-1)] font-mono text-[var(--text-xs)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:border-[var(--color-accent)] focus:outline-none"
        />
      </div>

      {/* Textarea */}
      <div className="relative">
        <textarea
          ref={textareaRef}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          rows={3}
          placeholder="Describe the task for the agent..."
          className="w-full resize-none bg-[var(--color-bg-surface)] px-[var(--space-4)] py-[var(--space-3)] font-mono text-[var(--text-sm)] text-[var(--color-text)] placeholder:text-[var(--color-text-muted)] focus:outline-none"
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!description.trim() || !selectedRepo || disabled}
          aria-label="Submit task"
          className="absolute right-[var(--space-3)] bottom-[var(--space-3)] rounded-[var(--radius-md)] bg-[var(--color-accent)] p-[var(--space-2)] text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)] disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      {/* Bottom hint */}
      <div className="border-t border-[var(--color-border)] px-[var(--space-4)] py-[var(--space-2)]">
        <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
          <kbd className="rounded border border-[var(--color-border-strong)] bg-[var(--color-bg-secondary)] px-1 py-0.5 font-mono text-[10px]">
            {"\u2318"}Enter
          </kbd>{" "}
          to submit &middot; Agent will create a branch from{" "}
          <span className="font-mono">{selectedRepoName}</span>
        </p>
      </div>
    </div>
  );
}
