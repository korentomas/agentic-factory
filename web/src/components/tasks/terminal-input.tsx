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
  const [repoUrl, setRepoUrl] = useState(repos[0]?.url ?? "");
  const [branch, setBranch] = useState("main");
  const [description, setDescription] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const handleSubmit = useCallback(() => {
    const text = description.trim();
    const url = repoUrl.trim();
    if (!text || !url || disabled) return;

    const firstLine = text.split("\n")[0] ?? text;
    onSubmit({
      repoUrl: url,
      branch,
      title: firstLine.slice(0, 120),
      description: text,
    });
    setDescription("");
  }, [description, repoUrl, branch, disabled, onSubmit]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit],
  );

  const displayName = repos.find((r) => r.url === repoUrl)?.fullName
    ?? (repoUrl.replace("https://github.com/", "") || "owner/repo");

  return (
    <div
      className={cn(
        "overflow-hidden rounded-lg border border-border bg-card shadow-sm",
        disabled && "opacity-60",
      )}
    >
      {/* Top bar */}
      <div className="flex items-center gap-2 border-b border-border px-4 py-3">
        <Terminal className="h-4 w-4 text-muted-foreground" />

        {repos.length > 0 ? (
          <select
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            disabled={disabled}
            className="rounded-sm border border-border bg-background px-2 py-1 font-mono text-xs text-foreground focus:border-primary focus:outline-none"
          >
            {repos.map((repo) => (
              <option key={repo.url} value={repo.url}>
                {repo.fullName}
              </option>
            ))}
          </select>
        ) : (
          <input
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            disabled={disabled}
            placeholder="https://github.com/owner/repo"
            className="min-w-0 flex-1 rounded-sm border border-border bg-background px-2 py-1 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
          />
        )}

        <span className="text-muted-foreground">/</span>

        <GitBranch className="h-3.5 w-3.5 text-muted-foreground" />
        <input
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          disabled={disabled}
          placeholder="main"
          className="w-28 rounded-sm border border-border bg-background px-2 py-1 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none"
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
          className="w-full resize-none bg-card px-4 py-3 font-mono text-sm text-foreground placeholder:text-muted-foreground focus:outline-none"
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={!description.trim() || !repoUrl.trim() || disabled}
          aria-label="Submit task"
          className="absolute right-3 bottom-3 rounded-md bg-primary p-2 text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>

      {/* Bottom hint */}
      <div className="border-t border-border px-4 py-2">
        <p className="text-xs text-muted-foreground">
          <kbd className="rounded border border-border bg-muted px-1 py-0.5 font-mono text-[10px]">
            {"\u2318"}Enter
          </kbd>{" "}
          to submit &middot; Agent will create a branch from{" "}
          <span className="font-mono">{displayName}</span>
        </p>
      </div>
    </div>
  );
}
