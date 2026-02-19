import type { DashboardStats } from "@/lib/data/types";

function formatDuration(ms: number): string {
  if (ms === 0) return "--";
  const seconds = Math.round(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.round(seconds / 60);
  return `${minutes}m`;
}

function formatCost(usd: number): string {
  if (usd === 0) return "$0";
  if (usd < 0.01) return "<$0.01";
  return `$${usd.toFixed(2)}`;
}

function formatRate(rate: number): string {
  if (rate === 0) return "--";
  return `${Math.round(rate * 100)}%`;
}

export function StatsCards({ stats }: { stats: DashboardStats }) {
  const cards = [
    {
      label: "Tasks this month",
      value: stats.tasksThisMonth.toString(),
      sub: `${stats.totalTasks} all time`,
    },
    {
      label: "PRs shipped",
      value: stats.prsClean.toString(),
      sub: `${stats.prsFailed} failed`,
    },
    {
      label: "Success rate",
      value: formatRate(stats.successRate),
      sub:
        stats.successRate >= 0.8
          ? "Healthy"
          : stats.successRate >= 0.5
            ? "Needs attention"
            : "Critical",
      highlight:
        stats.successRate >= 0.8
          ? "success"
          : stats.successRate >= 0.5
            ? "warning"
            : "error",
    },
    {
      label: "Avg duration",
      value: formatDuration(stats.avgDurationMs),
      sub: formatCost(stats.totalCost) + " total cost",
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-[var(--space-4)] sm:grid-cols-2 lg:grid-cols-4">
      {cards.map(({ label, value, sub, highlight }) => (
        <div
          key={label}
          className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]"
        >
          <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
            {label}
          </p>
          <p
            className={`mt-[var(--space-2)] text-[var(--text-3xl)] font-semibold tracking-tight ${
              highlight === "success"
                ? "text-[var(--color-success)]"
                : highlight === "warning"
                  ? "text-[var(--color-warning)]"
                  : highlight === "error"
                    ? "text-[var(--color-error)]"
                    : ""
            }`}
          >
            {value}
          </p>
          <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
            {sub}
          </p>
        </div>
      ))}
    </div>
  );
}
