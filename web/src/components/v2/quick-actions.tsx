"use client";

import { Dispatch, SetStateAction } from "react";
import { Card, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Badge } from "../ui/badge";
import { Skeleton } from "../ui/skeleton";
import {
  Bug,
  Plus,
  TestTube,
  Paintbrush,
  CircleDot,
  AlertCircle,
} from "lucide-react";
import useSWR from "swr";

/* ─────────────────────────────────────────────────────────
 * Types
 * ───────────────────────────────────────────────────────── */

interface IssueLabel {
  name: string;
  color: string;
}

interface IssueItem {
  title: string;
  number: number;
  repoFullName: string;
  url: string;
  labels: IssueLabel[];
}

/* ─────────────────────────────────────────────────────────
 * Fallback static actions (no brackets, natural language)
 * ───────────────────────────────────────────────────────── */

const FALLBACK_ACTIONS = [
  {
    title: "Fix a Bug",
    description: "Describe the bug and let the agent diagnose and fix it.",
    prompt:
      "I found a bug that needs investigation. The issue is: ",
    icon: Bug,
  },
  {
    title: "Add a Feature",
    description: "Describe the feature and the agent will implement it.",
    prompt:
      "Please implement the following feature: ",
    icon: Plus,
  },
  {
    title: "Write Tests",
    description: "Generate test coverage for existing code.",
    prompt:
      "Add comprehensive test coverage for the codebase, focusing on untested modules.",
    icon: TestTube,
  },
  {
    title: "Refactor Code",
    description: "Clean up and improve code quality.",
    prompt:
      "Refactor and improve code quality while keeping behavior identical.",
    icon: Paintbrush,
  },
] as const;

/* ─────────────────────────────────────────────────────────
 * Helpers
 * ───────────────────────────────────────────────────────── */

const fetcher = (url: string) => fetch(url).then((r) => r.json());

/** Build a task prompt from a GitHub issue. */
function issueToPrompt(issue: IssueItem): string {
  const bugLabels = ["bug", "error", "fix", "defect", "crash"];
  const isBug = issue.labels.some((l) =>
    bugLabels.includes(l.name.toLowerCase()),
  );

  const repoShort = issue.repoFullName.split("/")[1] ?? issue.repoFullName;

  if (isBug) {
    return `Fix issue #${issue.number} in ${repoShort}: "${issue.title}". Investigate the root cause and submit a fix with tests.`;
  }
  return `Implement issue #${issue.number} in ${repoShort}: "${issue.title}". Follow existing patterns in the codebase and add tests.`;
}

/** Pick an icon based on issue labels. */
function issueIcon(labels: IssueLabel[]): typeof Bug {
  const names = labels.map((l) => l.name.toLowerCase());
  if (names.some((n) => ["bug", "error", "fix", "defect", "crash"].includes(n)))
    return Bug;
  if (names.some((n) => ["enhancement", "feature", "feat"].includes(n)))
    return Plus;
  if (names.some((n) => ["test", "testing", "coverage"].includes(n)))
    return TestTube;
  return CircleDot;
}

/** Shorten a repo full name to just the repo portion. */
function repoShortName(fullName: string): string {
  return fullName.split("/")[1] ?? fullName;
}

/* ─────────────────────────────────────────────────────────
 * Loading skeleton
 * ───────────────────────────────────────────────────────── */

function QuickActionsSkeleton() {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <Card key={i} className="border-border bg-card py-3">
          <CardHeader className="px-3">
            <div className="flex items-center gap-2">
              <Skeleton className="h-4 w-4 rounded" />
              <Skeleton className="h-4 w-24" />
            </div>
            <Skeleton className="mt-1.5 h-3 w-full" />
          </CardHeader>
        </Card>
      ))}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────
 * Issue card
 * ───────────────────────────────────────────────────────── */

function IssueCard({
  issue,
  onClick,
}: {
  issue: IssueItem;
  onClick: () => void;
}) {
  const Icon = issueIcon(issue.labels);
  const repo = repoShortName(issue.repoFullName);

  return (
    <Card
      onClick={onClick}
      className="border-border bg-card hover:bg-muted/30 dark:hover:bg-muted/20 hover:shadow-primary/2 cursor-pointer py-3 transition-all duration-200 hover:shadow-sm"
    >
      <CardHeader className="px-3">
        <CardTitle className="text-foreground flex items-center gap-2 text-sm leading-snug">
          <Icon className="text-muted-foreground h-4 w-4 shrink-0" />
          <span className="line-clamp-1">
            #{issue.number} {issue.title}
          </span>
        </CardTitle>
        <CardDescription className="text-muted-foreground mt-1 flex items-center gap-1.5 text-xs">
          <span className="truncate">{repo}</span>
          {issue.labels.slice(0, 2).map((label) => (
            <Badge
              key={label.name}
              variant="outline"
              className="text-muted-foreground h-4 px-1 text-[10px]"
            >
              {label.name}
            </Badge>
          ))}
        </CardDescription>
      </CardHeader>
    </Card>
  );
}

/* ─────────────────────────────────────────────────────────
 * Fallback action card
 * ───────────────────────────────────────────────────────── */

function FallbackCard({
  action,
  onClick,
}: {
  action: (typeof FALLBACK_ACTIONS)[number];
  onClick: () => void;
}) {
  return (
    <Card
      onClick={onClick}
      className="border-border bg-card hover:bg-muted/30 dark:hover:bg-muted/20 hover:shadow-primary/2 cursor-pointer py-3 transition-all duration-200 hover:shadow-sm"
    >
      <CardHeader className="px-3">
        <CardTitle className="text-foreground flex items-center gap-2 text-sm">
          <action.icon className="text-muted-foreground h-4 w-4" />
          {action.title}
        </CardTitle>
        <CardDescription className="text-muted-foreground text-xs">
          {action.description}
        </CardDescription>
      </CardHeader>
    </Card>
  );
}

/* ─────────────────────────────────────────────────────────
 * Main component
 * ───────────────────────────────────────────────────────── */

interface QuickActionsProps {
  setQuickActionPrompt: Dispatch<SetStateAction<string>>;
  selectedRepo?: string;
}

export function QuickActions({
  setQuickActionPrompt,
  selectedRepo,
}: QuickActionsProps) {
  const queryParam = selectedRepo
    ? `?repo=${encodeURIComponent(selectedRepo)}`
    : "";

  const { data, isLoading, error } = useSWR<{ issues: IssueItem[] }>(
    `/api/repos/issues${queryParam}`,
    fetcher,
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
    },
  );

  const issues = data?.issues ?? [];
  const hasIssues = issues.length > 0;

  // Show loading skeleton on first load only
  if (isLoading && !data) {
    return (
      <div>
        <h2 className="text-foreground mb-3 text-base font-semibold">
          Suggested Tasks
        </h2>
        <QuickActionsSkeleton />
      </div>
    );
  }

  // If there was an error or no issues, show fallback actions
  if (error || !hasIssues) {
    return (
      <div>
        <h2 className="text-foreground mb-3 text-base font-semibold">
          Quick Actions
        </h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {FALLBACK_ACTIONS.map((action) => (
            <FallbackCard
              key={action.title}
              action={action}
              onClick={() => setQuickActionPrompt(action.prompt)}
            />
          ))}
        </div>
      </div>
    );
  }

  // Show contextual issues from GitHub
  const gridCols =
    issues.length <= 2
      ? "sm:grid-cols-2"
      : issues.length <= 4
        ? "sm:grid-cols-2 lg:grid-cols-4"
        : "sm:grid-cols-2 lg:grid-cols-3";

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <h2 className="text-foreground text-base font-semibold">
          Suggested Tasks
        </h2>
        <span className="text-muted-foreground flex items-center gap-1 text-xs">
          <AlertCircle className="h-3 w-3" />
          from open issues
        </span>
      </div>
      <div className={`grid gap-3 ${gridCols}`}>
        {issues.map((issue) => (
          <IssueCard
            key={`${issue.repoFullName}-${issue.number}`}
            issue={issue}
            onClick={() => setQuickActionPrompt(issueToPrompt(issue))}
          />
        ))}
      </div>
    </div>
  );
}
