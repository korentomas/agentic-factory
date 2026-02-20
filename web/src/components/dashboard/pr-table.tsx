"use client";

import { Fragment, useState } from "react";
import type { PRDetail } from "@/lib/data/types";

function OutcomeBadge({ outcome }: { outcome: PRDetail["outcome"] }) {
  const styles: Record<string, string> = {
    clean:
      "bg-[var(--color-success)]/10 text-[var(--color-success)] border-[var(--color-success)]/20",
    "review-failed":
      "bg-[var(--color-error)]/10 text-[var(--color-error)] border-[var(--color-error)]/20",
    "tests-failed":
      "bg-[var(--color-error)]/10 text-[var(--color-error)] border-[var(--color-error)]/20",
    blocked:
      "bg-[var(--color-warning)]/10 text-[var(--color-warning)] border-[var(--color-warning)]/20",
  };

  const labels: Record<string, string> = {
    clean: "Shipped",
    "review-failed": "Review Failed",
    "tests-failed": "Tests Failed",
    blocked: "Blocked",
  };

  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${styles[outcome] || ""}`}
    >
      {labels[outcome] || outcome}
    </span>
  );
}

function RiskBadge({ tier }: { tier: PRDetail["riskTier"] }) {
  const styles: Record<string, string> = {
    high: "text-[var(--color-error)]",
    medium: "text-[var(--color-warning)]",
    low: "text-muted-foreground",
  };

  return (
    <span className={`text-xs font-medium uppercase ${styles[tier]}`}>
      {tier}
    </span>
  );
}

function CheckDot({ status }: { status: "success" | "failure" | "skipped" }) {
  const colors: Record<string, string> = {
    success: "bg-[var(--color-success)]",
    failure: "bg-[var(--color-error)]",
    skipped: "bg-muted-foreground/30",
  };

  return (
    <span
      className={`inline-block h-2 w-2 rounded-full ${colors[status]}`}
      title={status}
    />
  );
}

function timeAgo(timestamp: string): string {
  const now = Date.now();
  const then = new Date(timestamp).getTime();
  const diff = now - then;

  const minutes = Math.floor(diff / 60000);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;

  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return new Date(timestamp).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

interface PRTableProps {
  prs: PRDetail[];
}

export function PRTable({ prs }: PRTableProps) {
  const [expanded, setExpanded] = useState<number | null>(null);

  if (prs.length === 0) {
    return (
      <div className="rounded-lg border border-dashed border-border p-12 text-center">
        <p className="text-muted-foreground">
          No PRs yet. Label a GitHub issue with{" "}
          <code className="rounded bg-muted px-2 py-1 font-mono text-sm">
            ai-agent
          </code>{" "}
          to get started.
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-border">
            <th className="pb-3 font-medium text-muted-foreground">
              PR
            </th>
            <th className="pb-3 font-medium text-muted-foreground">
              Status
            </th>
            <th className="hidden pb-3 font-medium text-muted-foreground md:table-cell">
              Risk
            </th>
            <th className="hidden pb-3 font-medium text-muted-foreground md:table-cell">
              Engine
            </th>
            <th className="hidden pb-3 font-medium text-muted-foreground lg:table-cell">
              Checks
            </th>
            <th className="hidden pb-3 font-medium text-muted-foreground lg:table-cell">
              Files
            </th>
            <th className="pb-3 text-right font-medium text-muted-foreground">
              When
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {prs.map((pr) => (
            <Fragment key={pr.number}>
              <tr
                className="cursor-pointer transition-colors hover:bg-muted"
                onClick={() =>
                  setExpanded(expanded === pr.number ? null : pr.number)
                }
              >
                <td className="py-3">
                  <a
                    href={pr.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary hover:underline"
                    onClick={(e) => e.stopPropagation()}
                  >
                    #{pr.number}
                  </a>
                  <span className="ml-2 text-foreground">
                    {pr.title}
                  </span>
                </td>
                <td className="py-3">
                  <OutcomeBadge outcome={pr.outcome} />
                </td>
                <td className="hidden py-3 md:table-cell">
                  <RiskBadge tier={pr.riskTier} />
                </td>
                <td className="hidden py-3 md:table-cell">
                  <span className="text-muted-foreground">
                    {pr.engine}
                  </span>
                </td>
                <td className="hidden py-3 lg:table-cell">
                  <div className="flex items-center gap-1">
                    <CheckDot status={pr.checksStatus.gate} />
                    <CheckDot status={pr.checksStatus.tests} />
                    <CheckDot status={pr.checksStatus.review} />
                    <CheckDot status={pr.checksStatus.spec_audit} />
                  </div>
                </td>
                <td className="hidden py-3 lg:table-cell">
                  <span className="text-muted-foreground">
                    {pr.filesChanged.length}
                  </span>
                </td>
                <td className="py-3 text-right text-muted-foreground">
                  {timeAgo(pr.timestamp)}
                </td>
              </tr>

              {expanded === pr.number && (
                <tr>
                  <td
                    colSpan={7}
                    className="bg-muted px-6 py-4"
                  >
                    <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
                      <div>
                        <p className="text-muted-foreground">Model</p>
                        <p className="mt-1 font-mono text-xs">
                          {pr.model}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">
                          Cost
                        </p>
                        <p className="mt-1">
                          {pr.cost > 0 ? `$${pr.cost.toFixed(2)}` : "N/A"}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">
                          Duration
                        </p>
                        <p className="mt-1">
                          {pr.duration > 0
                            ? `${Math.round(pr.duration / 1000)}s`
                            : "N/A"}
                        </p>
                      </div>
                      <div>
                        <p className="text-muted-foreground">
                          Turns
                        </p>
                        <p className="mt-1">
                          {pr.numTurns > 0 ? pr.numTurns : "N/A"}
                        </p>
                      </div>
                    </div>

                    {pr.filesChanged.length > 0 && (
                      <div className="mt-4">
                        <p className="text-xs text-muted-foreground">
                          Files changed
                        </p>
                        <div className="mt-2 flex flex-wrap gap-1">
                          {pr.filesChanged.map((f) => (
                            <span
                              key={f}
                              className="rounded bg-background px-2 py-0.5 font-mono text-xs text-muted-foreground"
                            >
                              {f}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="mt-4 flex items-center gap-4">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-muted-foreground">
                          Gate
                        </span>
                        <CheckDot status={pr.checksStatus.gate} />
                        <span className="text-muted-foreground">
                          Tests
                        </span>
                        <CheckDot status={pr.checksStatus.tests} />
                        <span className="text-muted-foreground">
                          Review
                        </span>
                        <CheckDot status={pr.checksStatus.review} />
                        <span className="text-muted-foreground">
                          Spec Audit
                        </span>
                        <CheckDot status={pr.checksStatus.spec_audit} />
                      </div>
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
