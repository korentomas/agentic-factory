"use client";

import type React from "react";
import { useEffect, useState, Dispatch, SetStateAction } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ArrowUp, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import useSWR from "swr";
import type { RepoOption } from "./types";

interface TerminalInputProps {
  placeholder?: string;
  disabled?: boolean;
  quickActionPrompt?: string;
  setQuickActionPrompt?: Dispatch<SetStateAction<string>>;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

function slugify(text: string): string {
  return text
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 40);
}

export function TerminalInput({
  placeholder = "Describe your coding task...",
  disabled = false,
  quickActionPrompt,
  setQuickActionPrompt,
}: TerminalInputProps) {
  const router = useRouter();
  const [message, setMessage] = useState("");
  const [selectedRepo, setSelectedRepo] = useState("");
  const [branch, setBranch] = useState("");
  const [loading, setLoading] = useState(false);

  const { data: repoData } = useSWR<{ repos: RepoOption[] }>(
    "/api/repos",
    fetcher,
  );
  const repos = repoData?.repos ?? [];

  useEffect(() => {
    if (quickActionPrompt && message !== quickActionPrompt) {
      setMessage(quickActionPrompt);
      setQuickActionPrompt?.("");
    }
  }, [quickActionPrompt, message, setQuickActionPrompt]);

  const handleSend = async () => {
    const trimmed = message.trim();
    if (!trimmed) return;

    if (!selectedRepo) {
      toast.error("Please select a repository first", {
        richColors: true,
        closeButton: true,
      });
      return;
    }

    setLoading(true);

    const repo = repos.find((r) => r.fullName === selectedRepo);
    const repoUrl = repo?.url ?? `https://github.com/${selectedRepo}`;
    const title = trimmed.slice(0, 120);
    const taskBranch =
      branch.trim() || `lailatov/${slugify(title)}-${Date.now().toString(36)}`;

    try {
      const res = await fetch("/api/tasks/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repoUrl,
          branch: taskBranch,
          title,
          description: trimmed,
        }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Request failed" }));
        toast.error(err.error ?? "Failed to create task", {
          richColors: true,
          closeButton: true,
        });
        return;
      }

      const { threadId } = await res.json();
      setMessage("");
      setBranch("");
      router.push(`/chat/${threadId}`);
    } catch (err) {
      toast.error("Network error — could not create task", {
        richColors: true,
        closeButton: true,
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-border bg-muted hover:border-muted-foreground/50 focus-within:border-muted-foreground/70 focus-within:shadow-muted-foreground/20 rounded-md border p-3 font-mono text-xs transition-all duration-200 focus-within:shadow-md">
      {/* Textarea — hero element */}
      <Textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={disabled || loading}
        className="text-foreground placeholder:text-muted-foreground max-h-[50vh] min-h-[120px] resize-none border-none bg-transparent p-0 font-mono text-xs shadow-none focus-visible:ring-0 focus-visible:ring-offset-0"
        rows={6}
      />

      {/* Secondary row: repo + branch + send */}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Select value={selectedRepo} onValueChange={setSelectedRepo}>
          <SelectTrigger
            size="sm"
            className="border-border bg-background/50 h-7 w-auto min-w-[160px] text-xs"
          >
            <SelectValue placeholder="Select repo" />
          </SelectTrigger>
          <SelectContent>
            {repos.length === 0 ? (
              <SelectItem value="__none" disabled>
                No repos connected
              </SelectItem>
            ) : (
              repos.map((repo) => (
                <SelectItem key={repo.fullName} value={repo.fullName}>
                  {repo.fullName}
                </SelectItem>
              ))
            )}
          </SelectContent>
        </Select>

        <input
          type="text"
          value={branch}
          onChange={(e) => setBranch(e.target.value)}
          placeholder="branch (auto)"
          className="border-border bg-background/50 text-foreground placeholder:text-muted-foreground h-7 rounded-md border px-2 text-xs outline-none"
        />

        <div className="ml-auto flex items-center gap-3">
          <span className="text-muted-foreground text-xs">
            <kbd className="bg-background/50 rounded px-1 py-0.5 text-[10px]">
              Cmd+Enter
            </kbd>
          </span>
          <Button
            onClick={handleSend}
            disabled={disabled || !message.trim() || !selectedRepo || loading}
            size="icon"
            variant="brand"
            className="size-8 rounded-full border border-white/20 transition-all duration-200 hover:border-white/30 disabled:border-transparent"
          >
            {loading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <ArrowUp className="size-4" />
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}
