import type { CodeRetention } from "@/lib/data/types";

export function CodeRetentionPanel({
  retention,
}: {
  retention: CodeRetention[];
}) {
  if (retention.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="text-base font-medium">
          Code Retention
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          How much agent-written code survives in the codebase
        </p>

        <div className="mt-6 rounded-md border border-dashed border-border p-8 text-center">
          <p className="text-sm text-muted-foreground">
            Retention data appears after PRs are merged. Connect your GitHub
            account to see how agent code persists in your codebase.
          </p>
        </div>
      </div>
    );
  }

  // Aggregate stats
  const totalWritten = retention.reduce((s, r) => s + r.linesWritten, 0);
  const totalRetained = retention.reduce((s, r) => s + r.linesRetained, 0);
  const totalOverwrittenAgent = retention.reduce(
    (s, r) => s + r.overwrittenByAgent,
    0
  );
  const totalOverwrittenHuman = retention.reduce(
    (s, r) => s + r.overwrittenByHuman,
    0
  );
  const overallRetention = totalWritten > 0 ? totalRetained / totalWritten : 0;

  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <h3 className="text-base font-medium">Code Retention</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        How much agent-written code survives in the codebase
      </p>

      {/* Overall retention gauge */}
      <div className="mt-6 flex items-center gap-6">
        <div className="relative h-24 w-24 shrink-0">
          <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
            {/* Background circle */}
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke="hsl(var(--muted))"
              strokeWidth="8"
            />
            {/* Retention arc */}
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke="hsl(var(--primary))"
              strokeWidth="8"
              strokeDasharray={`${overallRetention * 264} 264`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xl font-semibold">
              {Math.round(overallRetention * 100)}%
            </span>
          </div>
        </div>

        <div className="flex-1 space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-muted-foreground">Lines written by agent</span>
            <span className="font-medium">{totalWritten.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-[var(--color-success)]">Still in codebase</span>
            <span className="font-medium">{totalRetained.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-primary">
              Overwritten by agent
            </span>
            <span className="font-medium">
              {totalOverwrittenAgent.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-[var(--color-error)]">
              Overwritten by human
            </span>
            <span className="font-medium">
              {totalOverwrittenHuman.toLocaleString()}
            </span>
          </div>
        </div>
      </div>

      {/* Per-PR retention */}
      <div className="mt-6 space-y-3">
        <h4 className="text-sm font-medium text-muted-foreground">
          Per-PR Breakdown
        </h4>
        {retention.map((r) => (
          <div
            key={r.prNumber}
            className="rounded-md bg-muted p-3"
          >
            <div className="flex items-center justify-between">
              <a
                href={r.prUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm font-medium text-primary hover:underline"
              >
                PR #{r.prNumber}
              </a>
              <span className="text-sm font-medium">
                {Math.round(r.retentionRate * 100)}% retained
              </span>
            </div>

            {/* Stacked bar */}
            <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-background">
              {r.linesRetained > 0 && (
                <div
                  className="bg-[var(--color-success)]"
                  style={{
                    width: `${(r.linesRetained / r.linesWritten) * 100}%`,
                  }}
                />
              )}
              {r.overwrittenByAgent > 0 && (
                <div
                  className="bg-primary"
                  style={{
                    width: `${(r.overwrittenByAgent / r.linesWritten) * 100}%`,
                  }}
                />
              )}
              {r.overwrittenByHuman > 0 && (
                <div
                  className="bg-[var(--color-error)]"
                  style={{
                    width: `${(r.overwrittenByHuman / r.linesWritten) * 100}%`,
                  }}
                />
              )}
            </div>

            <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
              <span>{r.linesWritten} lines</span>
              <span>{r.filesChanged.length} files</span>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mt-4 flex flex-wrap gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-[var(--color-success)]" />
          Retained
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-primary" />
          Agent overwrite
        </span>
        <span className="flex items-center gap-1">
          <span className="h-2 w-2 rounded-full bg-[var(--color-error)]" />
          Human overwrite
        </span>
      </div>
    </div>
  );
}
