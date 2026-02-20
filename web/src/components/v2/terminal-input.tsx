"use client";

import type React from "react";
import { useEffect, useState, useCallback, Dispatch, SetStateAction } from "react";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from "@/components/ui/command";
import { ArrowUp, Check, ChevronsUpDown, GitBranch, Loader2, Shield } from "lucide-react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import useSWR from "swr";
import { cn } from "@/lib/utils";
import type { RepoOption, BranchOption } from "./types";

interface TerminalInputProps {
  placeholder?: string;
  disabled?: boolean;
  quickActionPrompt?: string;
  setQuickActionPrompt?: Dispatch<SetStateAction<string>>;
}

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const SELECTED_REPO_KEY = "lailatov_selected_repo";

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
  const [selectedBranch, setSelectedBranch] = useState("");
  const [loading, setLoading] = useState(false);
  const [repoOpen, setRepoOpen] = useState(false);
  const [branchOpen, setBranchOpen] = useState(false);

  const { data: repoData } = useSWR<{ repos: RepoOption[] }>(
    "/api/repos",
    fetcher,
  );
  const repos = repoData?.repos ?? [];

  // Parse owner/repo for branch API
  const [owner, repo] = selectedRepo ? selectedRepo.split("/") : [null, null];
  const { data: branchData, isLoading: branchesLoading } = useSWR<{
    defaultBranch: string;
    branches: BranchOption[];
  }>(
    owner && repo ? `/api/repos/${owner}/${repo}/branches` : null,
    fetcher,
  );
  const branches = branchData?.branches ?? [];
  const defaultBranch = branchData?.defaultBranch ?? "";

  // Auto-select repo: restore from localStorage or pick first
  useEffect(() => {
    if (repos.length === 0 || selectedRepo) return;

    const stored = localStorage.getItem(SELECTED_REPO_KEY);
    if (stored && repos.some((r) => r.fullName === stored)) {
      setSelectedRepo(stored);
    } else {
      setSelectedRepo(repos[0].fullName);
      localStorage.setItem(SELECTED_REPO_KEY, repos[0].fullName);
    }
  }, [repos, selectedRepo]);

  // Auto-select default branch when branches load or repo changes
  useEffect(() => {
    if (branches.length === 0) return;

    // If current selection exists in new branch list, keep it
    if (selectedBranch && branches.some((b) => b.name === selectedBranch)) {
      return;
    }

    // Select default branch, or first branch as fallback
    const target = defaultBranch || branches[0].name;
    setSelectedBranch(target);
  }, [branches, defaultBranch, selectedBranch]);

  // Persist repo selection
  const handleRepoSelect = useCallback(
    (fullName: string) => {
      setSelectedRepo(fullName);
      setSelectedBranch(""); // Reset branch when repo changes
      localStorage.setItem(SELECTED_REPO_KEY, fullName);
      setRepoOpen(false);
    },
    [],
  );

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

    const repoObj = repos.find((r) => r.fullName === selectedRepo);
    const repoUrl = repoObj?.url ?? `https://github.com/${selectedRepo}`;
    const title = trimmed.slice(0, 120);
    const taskBranch =
      selectedBranch === defaultBranch || !selectedBranch
        ? `lailatov/${slugify(title)}-${Date.now().toString(36)}`
        : selectedBranch;

    try {
      const res = await fetch("/api/tasks/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repoUrl,
          branch: taskBranch,
          baseBranch: selectedBranch || defaultBranch || "main",
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
      router.push(`/chat/${threadId}`);
    } catch {
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
        {/* Repo selector — searchable combobox */}
        <Popover open={repoOpen} onOpenChange={setRepoOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={repoOpen}
              className="border-border bg-background/50 h-7 w-auto min-w-[160px] justify-between px-2 text-xs font-normal"
            >
              <span className="truncate">
                {selectedRepo || "Select repo..."}
              </span>
              <ChevronsUpDown className="ml-1 h-3 w-3 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[280px] p-0" align="start">
            <Command>
              <CommandInput placeholder="Search repos..." className="text-xs" />
              <CommandList>
                <CommandEmpty>No repos found.</CommandEmpty>
                <CommandGroup>
                  {repos.map((r) => (
                    <CommandItem
                      key={r.fullName}
                      value={r.fullName}
                      onSelect={handleRepoSelect}
                      className="text-xs"
                    >
                      <Check
                        className={cn(
                          "mr-2 h-3 w-3",
                          selectedRepo === r.fullName
                            ? "opacity-100"
                            : "opacity-0",
                        )}
                      />
                      {r.fullName}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>

        {/* Branch selector — searchable dropdown */}
        <Popover open={branchOpen} onOpenChange={setBranchOpen}>
          <PopoverTrigger asChild>
            <Button
              variant="outline"
              role="combobox"
              aria-expanded={branchOpen}
              disabled={!selectedRepo || branchesLoading}
              className="border-border bg-background/50 h-7 w-auto min-w-[140px] justify-between px-2 text-xs font-normal"
            >
              <GitBranch className="mr-1 h-3 w-3 shrink-0 opacity-70" />
              <span className="truncate">
                {branchesLoading
                  ? "Loading..."
                  : selectedBranch || "Select branch..."}
              </span>
              <ChevronsUpDown className="ml-1 h-3 w-3 shrink-0 opacity-50" />
            </Button>
          </PopoverTrigger>
          <PopoverContent className="w-[240px] p-0" align="start">
            <Command>
              <CommandInput
                placeholder="Search branches..."
                className="text-xs"
              />
              <CommandList>
                <CommandEmpty>No branches found.</CommandEmpty>
                <CommandGroup>
                  {branches.map((b) => (
                    <CommandItem
                      key={b.name}
                      value={b.name}
                      onSelect={(val) => {
                        setSelectedBranch(val);
                        setBranchOpen(false);
                      }}
                      className="text-xs"
                    >
                      <Check
                        className={cn(
                          "mr-2 h-3 w-3",
                          selectedBranch === b.name
                            ? "opacity-100"
                            : "opacity-0",
                        )}
                      />
                      <span className="truncate">{b.name}</span>
                      {b.isDefault && (
                        <span className="ml-auto rounded bg-blue-500/10 px-1 py-0.5 text-[10px] text-blue-500">
                          default
                        </span>
                      )}
                      {b.protected && (
                        <Shield className="ml-1 h-3 w-3 text-amber-500" />
                      )}
                    </CommandItem>
                  ))}
                </CommandGroup>
              </CommandList>
            </Command>
          </PopoverContent>
        </Popover>

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
