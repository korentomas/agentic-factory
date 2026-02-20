"use client";

import {
  CheckCircle,
  GitBranch,
  AlertCircle,
  XCircle,
  Clock,
  Loader2,
  DollarSign,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { useRouter } from "next/navigation";
import { Badge } from "../ui/badge";
import { Skeleton } from "../ui/skeleton";
import type { ThreadMetadata, ThreadStatus } from "./types";
import { cn } from "@/lib/utils";

interface ThreadCardProps {
  thread: ThreadMetadata;
  status?: ThreadStatus;
  statusLoading?: boolean;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  if (minutes < 60) return `${minutes}m ${remainingSeconds}s`;
  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;
  return `${hours}h ${remainingMinutes}m`;
}

function formatRelativeTime(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - new Date(date).getTime();
  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 1) return "just now";
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 7) return `${diffDays}d ago`;
  return new Date(date).toLocaleDateString();
}

function getStatusColor(status: ThreadStatus): string {
  switch (status) {
    case "running":
      return "bg-blue-100 dark:bg-blue-950/50 text-blue-700 dark:text-blue-300";
    case "complete":
      return "bg-green-100 dark:bg-green-950/50 text-green-700 dark:text-green-300";
    case "committing":
      return "bg-amber-100 dark:bg-amber-950/50 text-amber-700 dark:text-amber-300";
    case "failed":
      return "bg-red-100 dark:bg-red-950/50 text-red-700 dark:text-red-300";
    case "cancelled":
      return "bg-gray-100 dark:bg-gray-800/50 text-gray-600 dark:text-gray-400";
    case "pending":
    default:
      return "bg-yellow-100 dark:bg-yellow-950/50 text-yellow-700 dark:text-yellow-300";
  }
}

function getStatusIcon(status: ThreadStatus) {
  switch (status) {
    case "running":
      return <Loader2 className="h-3.5 w-3.5 animate-spin" />;
    case "complete":
      return <CheckCircle className="h-3.5 w-3.5" />;
    case "committing":
      return <Loader2 className="h-3.5 w-3.5 animate-spin" />;
    case "failed":
      return <XCircle className="h-3.5 w-3.5" />;
    case "cancelled":
      return <AlertCircle className="h-3.5 w-3.5" />;
    case "pending":
    default:
      return <Clock className="h-3.5 w-3.5" />;
  }
}

function extractRepoName(repoUrl: string): string {
  try {
    const url = new URL(repoUrl);
    return url.pathname.replace(/^\//, "").replace(/\.git$/, "");
  } catch {
    return repoUrl;
  }
}

export function ThreadCard({ thread, status, statusLoading }: ThreadCardProps) {
  const router = useRouter();
  const isStatusLoading = statusLoading && !status;
  const displayStatus = status ?? thread.status;
  const repoName = extractRepoName(thread.repository);

  return (
    <Card
      className="border-border bg-card hover:bg-muted/50 hover:shadow-primary/3 hover:border-primary/10 group cursor-pointer px-0 py-3 transition-all duration-200 hover:shadow-md"
      onClick={() => router.push(`/chat/${thread.id}`)}
    >
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <CardTitle className="text-foreground line-clamp-2 text-sm leading-tight">
              {thread.title}
            </CardTitle>
            <div className="mt-1.5 flex items-center gap-1.5">
              <GitBranch className="text-muted-foreground h-3 w-3 shrink-0" />
              <span className="text-muted-foreground truncate text-xs">
                {repoName}
              </span>
            </div>
          </div>
          <Badge
            variant="secondary"
            className={cn(
              "shrink-0 text-xs transition-all duration-300 group-hover:scale-105",
              isStatusLoading
                ? "dark:bg-muted dark:text-muted-foreground bg-gray-200 text-gray-600"
                : getStatusColor(displayStatus),
            )}
          >
            <div className="flex items-center gap-1">
              {isStatusLoading ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <div className="transition-transform duration-300 group-hover:rotate-12">
                  {getStatusIcon(displayStatus)}
                </div>
              )}
              <span className="capitalize">
                {isStatusLoading ? "Loading..." : displayStatus}
              </span>
            </div>
          </Badge>
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            {thread.engine && (
              <>
                <span className="text-muted-foreground text-xs">
                  {thread.engine}
                </span>
                <span className="text-muted-foreground text-xs">&middot;</span>
              </>
            )}
            {thread.durationMs > 0 && (
              <>
                <span className="text-muted-foreground text-xs">
                  {formatDuration(thread.durationMs)}
                </span>
                <span className="text-muted-foreground text-xs">&middot;</span>
              </>
            )}
            <span className="text-muted-foreground text-xs">
              {formatRelativeTime(thread.lastActivity)}
            </span>
          </div>
          {thread.costUsd > 0 && (
            <div className="text-muted-foreground flex items-center gap-0.5 text-xs">
              <DollarSign className="h-3 w-3" />
              {thread.costUsd.toFixed(2)}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function ThreadCardLoading() {
  return (
    <Card className="border-border bg-card px-0 py-3">
      <CardHeader>
        <div className="flex items-start justify-between">
          <div className="min-w-0 flex-1">
            <Skeleton className="h-5 w-48" />
            <div className="mt-1.5 flex items-center gap-1.5">
              <Skeleton className="h-3 w-3 rounded-full" />
              <Skeleton className="h-3 w-32" />
            </div>
          </div>
          <Skeleton className="h-6 w-24 rounded-full" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Skeleton className="h-3 w-16" />
            <Skeleton className="h-3 w-1" />
            <Skeleton className="h-3 w-24" />
          </div>
          <Skeleton className="h-3 w-12" />
        </div>
      </CardContent>
    </Card>
  );
}
