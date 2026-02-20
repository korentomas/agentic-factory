"use client";

import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Code2,
  FileText,
  GitBranch,
  Loader2,
  Search,
  Terminal,
  TestTube,
  Wrench,
  AlertCircle,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { LoadingActionsCardContent } from "./thread-view-loading";
import type { TaskMessage, ThreadStatus } from "./types";

interface ActionsRendererProps {
  messages: TaskMessage[];
  threadStatus: ThreadStatus;
  isStreaming: boolean;
}

interface ToolStep {
  id: string;
  toolName: string;
  toolInput: string | null;
  toolOutput: string | null;
  timestamp: Date;
  isLast: boolean;
}

function getToolIcon(toolName: string) {
  const lower = toolName.toLowerCase();
  if (lower.includes("bash") || lower.includes("shell") || lower.includes("exec")) {
    return Terminal;
  }
  if (lower.includes("read") || lower.includes("file") || lower.includes("cat")) {
    return FileText;
  }
  if (lower.includes("write") || lower.includes("edit") || lower.includes("patch")) {
    return Code2;
  }
  return Wrench;
}

function getStepStatus(
  step: ToolStep,
  threadStatus: ThreadStatus,
  isStreaming: boolean,
): "running" | "complete" | "failed" {
  if (step.isLast && isStreaming) return "running";
  if (threadStatus === "failed" && step.isLast) return "failed";
  return "complete";
}

function StepStatusIcon({ status }: { status: "running" | "complete" | "failed" }) {
  switch (status) {
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
    case "complete":
      return <CheckCircle2 className="h-4 w-4 text-green-500" />;
    case "failed":
      return <AlertCircle className="h-4 w-4 text-red-500" />;
  }
}

function ToolStepCard({
  step,
  threadStatus,
  isStreaming,
}: {
  step: ToolStep;
  threadStatus: ThreadStatus;
  isStreaming: boolean;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const status = getStepStatus(step, threadStatus, isStreaming);
  const Icon = getToolIcon(step.toolName);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="hover:bg-muted/50 flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors">
        <StepStatusIcon status={status} />
        <Icon className="text-muted-foreground h-4 w-4 flex-shrink-0" />
        <div className="min-w-0 flex-1">
          <span className="text-sm font-medium">{step.toolName}</span>
        </div>
        <Badge
          variant="outline"
          className={cn(
            "text-xs",
            status === "running" && "border-blue-200 text-blue-600 dark:border-blue-800 dark:text-blue-400",
            status === "failed" && "border-red-200 text-red-600 dark:border-red-800 dark:text-red-400",
          )}
        >
          {status}
        </Badge>
        {isOpen ? (
          <ChevronDown className="text-muted-foreground h-4 w-4 flex-shrink-0" />
        ) : (
          <ChevronRight className="text-muted-foreground h-4 w-4 flex-shrink-0" />
        )}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="space-y-2 px-3 pb-3 pt-1">
          {step.toolInput && (
            <div className="space-y-1">
              <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                Input
              </span>
              <pre className="bg-muted/50 max-h-48 overflow-auto rounded-md p-2 font-mono text-xs">
                {step.toolInput}
              </pre>
            </div>
          )}
          {step.toolOutput && (
            <div className="space-y-1">
              <span className="text-muted-foreground text-xs font-medium uppercase tracking-wide">
                Output
              </span>
              <pre className="bg-muted/50 max-h-48 overflow-auto rounded-md p-2 font-mono text-xs">
                {step.toolOutput}
              </pre>
            </div>
          )}
          {!step.toolInput && !step.toolOutput && (
            <span className="text-muted-foreground text-xs italic">
              No details available
            </span>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function AssistantThinkingCard({ content }: { content: string }) {
  const [isOpen, setIsOpen] = useState(false);

  const preview =
    content.length > 120 ? content.slice(0, 120) + "..." : content;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="hover:bg-muted/50 flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors">
        <Code2 className="text-muted-foreground h-4 w-4 flex-shrink-0" />
        <span className="text-muted-foreground min-w-0 flex-1 truncate text-sm">
          {preview}
        </span>
        {isOpen ? (
          <ChevronDown className="text-muted-foreground h-4 w-4 flex-shrink-0" />
        ) : (
          <ChevronRight className="text-muted-foreground h-4 w-4 flex-shrink-0" />
        )}
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="px-3 pb-3 pt-1">
          <pre className="bg-muted/50 max-h-64 overflow-auto whitespace-pre-wrap rounded-md p-3 text-sm">
            {content}
          </pre>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

// --- Phase grouping logic ---

type Phase = "planning" | "coding" | "testing" | "committing" | "other";

const PHASE_CONFIG: Record<
  Phase,
  { label: string; icon: typeof Search; borderClass: string; badgeClass: string }
> = {
  planning: {
    label: "Planning",
    icon: Search,
    borderClass: "border-blue-300 dark:border-blue-800",
    badgeClass: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  },
  coding: {
    label: "Coding",
    icon: Code2,
    borderClass: "border-green-300 dark:border-green-800",
    badgeClass: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
  },
  testing: {
    label: "Testing",
    icon: TestTube,
    borderClass: "border-amber-300 dark:border-amber-800",
    badgeClass: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  },
  committing: {
    label: "Committing",
    icon: GitBranch,
    borderClass: "border-purple-300 dark:border-purple-800",
    badgeClass: "bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
  },
  other: {
    label: "Other",
    icon: Wrench,
    borderClass: "border-gray-300 dark:border-gray-700",
    badgeClass: "bg-gray-50 text-gray-700 dark:bg-gray-900 dark:text-gray-300",
  },
};

function classifyPhase(toolName: string): Phase {
  const lower = toolName.toLowerCase();

  // Testing patterns (check before coding — "bash" running tests should be testing)
  if (
    lower.includes("test") ||
    lower.includes("pytest") ||
    lower.includes("jest") ||
    lower.includes("vitest") ||
    lower.includes("check") ||
    lower.includes("lint") ||
    lower.includes("ruff") ||
    lower.includes("mypy")
  ) {
    return "testing";
  }

  // Committing patterns
  if (
    lower.includes("git") ||
    lower.includes("commit") ||
    lower.includes("push") ||
    lower.includes("pr") ||
    lower.includes("branch")
  ) {
    return "committing";
  }

  // Planning patterns
  if (
    lower.includes("read") ||
    lower.includes("glob") ||
    lower.includes("grep") ||
    lower.includes("search") ||
    lower.includes("list") ||
    lower.includes("cat") ||
    lower.includes("find") ||
    lower.includes("explore")
  ) {
    return "planning";
  }

  // Coding patterns
  if (
    lower.includes("write") ||
    lower.includes("edit") ||
    lower.includes("patch") ||
    lower.includes("create") ||
    lower.includes("bash") ||
    lower.includes("shell") ||
    lower.includes("exec")
  ) {
    return "coding";
  }

  return "other";
}

interface PhaseGroup {
  phase: Phase;
  entries: Array<{ type: "tool"; data: ToolStep } | { type: "assistant"; data: TaskMessage }>;
}

function groupEntriesByPhase(
  entries: Array<{ type: "tool" | "assistant"; data: ToolStep | TaskMessage; time: Date }>,
): PhaseGroup[] {
  const groups: PhaseGroup[] = [];
  let currentPhase: Phase | null = null;

  for (const entry of entries) {
    const phase: Phase =
      entry.type === "tool" ? classifyPhase((entry.data as ToolStep).toolName) : currentPhase ?? "other";

    if (phase !== currentPhase || groups.length === 0) {
      groups.push({ phase, entries: [] });
      currentPhase = phase;
    }

    groups[groups.length - 1].entries.push(
      entry as { type: "tool"; data: ToolStep } | { type: "assistant"; data: TaskMessage },
    );
  }

  return groups;
}

function PhaseSection({
  group,
  threadStatus,
  isStreaming,
}: {
  group: PhaseGroup;
  threadStatus: ThreadStatus;
  isStreaming: boolean;
}) {
  const [isOpen, setIsOpen] = useState(true);
  const config = PHASE_CONFIG[group.phase];
  const Icon = config.icon;
  const toolCount = group.entries.filter((e) => e.type === "tool").length;

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger className="hover:bg-muted/50 flex w-full items-center gap-2 rounded-md px-3 py-1.5 text-left transition-colors">
        {isOpen ? (
          <ChevronDown className="text-muted-foreground h-3 w-3 flex-shrink-0" />
        ) : (
          <ChevronRight className="text-muted-foreground h-3 w-3 flex-shrink-0" />
        )}
        <Icon className="text-muted-foreground h-3.5 w-3.5 flex-shrink-0" />
        <span className="text-muted-foreground text-xs font-medium">{config.label}</span>
        <span
          className={cn(
            "rounded-full px-1.5 py-0.5 text-[10px] font-medium leading-none",
            config.badgeClass,
          )}
        >
          {toolCount}
        </span>
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className={cn("ml-3 border-l-2 pl-1", config.borderClass)}>
          {group.entries.map((entry) => {
            if (entry.type === "tool") {
              const step = entry.data as ToolStep;
              return (
                <ToolStepCard
                  key={step.id}
                  step={step}
                  threadStatus={threadStatus}
                  isStreaming={isStreaming}
                />
              );
            }
            const msg = entry.data as TaskMessage;
            return <AssistantThinkingCard key={msg.id} content={msg.content} />;
          })}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

export function ActionsRenderer({
  messages,
  threadStatus,
  isStreaming,
}: ActionsRendererProps) {
  const toolSteps = useMemo<ToolStep[]>(() => {
    const tools = messages.filter(
      (m) => m.role === "tool" && m.toolName,
    );
    return tools.map((m, i) => ({
      id: m.id,
      toolName: m.toolName!,
      toolInput: m.toolInput ?? null,
      toolOutput: m.toolOutput ?? null,
      timestamp: m.createdAt,
      isLast: i === tools.length - 1,
    }));
  }, [messages]);

  const assistantMessages = useMemo(() => {
    return messages.filter(
      (m) => m.role === "assistant" && m.content,
    );
  }, [messages]);

  // All hooks must be called before early returns
  const allEntries = useMemo(() => {
    return [
      ...toolSteps.map((s) => ({ type: "tool" as const, data: s, time: s.timestamp })),
      ...assistantMessages.map((m) => ({ type: "assistant" as const, data: m, time: m.createdAt })),
    ].sort((a, b) => new Date(a.time).getTime() - new Date(b.time).getTime());
  }, [toolSteps, assistantMessages]);

  const shouldGroupPhases = toolSteps.length >= 5;
  const phaseGroups = useMemo(() => {
    if (!shouldGroupPhases) return [] as PhaseGroup[];
    return groupEntriesByPhase(allEntries);
  }, [shouldGroupPhases, allEntries]);

  const hasContent = toolSteps.length > 0 || assistantMessages.length > 0;

  if (!hasContent && isStreaming) {
    return <LoadingActionsCardContent />;
  }

  if (!hasContent) {
    return (
      <div className="flex items-center justify-center gap-2 py-8">
        <Clock className="text-muted-foreground h-4 w-4" />
        <span className="text-muted-foreground text-sm">
          No actions yet
        </span>
      </div>
    );
  }

  return (
    <div className="flex h-full w-full flex-col gap-1 overflow-y-auto py-4">
      {shouldGroupPhases
        ? phaseGroups.map((group, i) => (
            <PhaseSection
              key={`${group.phase}-${i}`}
              group={group}
              threadStatus={threadStatus}
              isStreaming={isStreaming}
            />
          ))
        : allEntries.map((entry) => {
            if (entry.type === "tool") {
              return (
                <ToolStepCard
                  key={entry.data.id}
                  step={entry.data}
                  threadStatus={threadStatus}
                  isStreaming={isStreaming}
                />
              );
            }
            return (
              <AssistantThinkingCard
                key={entry.data.id}
                content={entry.data.content}
              />
            );
          })}
      {isStreaming && toolSteps.length > 0 && (
        <div className="flex items-center gap-2 px-3 py-2">
          <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
          <span className="text-muted-foreground text-xs">
            Agent is working...
          </span>
        </div>
      )}
    </div>
  );
}
