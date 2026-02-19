import type { CodeRetention } from "@/lib/data/types";

export function CodeRetentionPanel({
  retention,
}: {
  retention: CodeRetention[];
}) {
  if (retention.length === 0) {
    return (
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
        <h3 className="text-[var(--text-base)] font-medium">
          Code Retention
        </h3>
        <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
          How much agent-written code survives in the codebase
        </p>

        <div className="mt-[var(--space-6)] rounded-[var(--radius-md)] border border-dashed border-[var(--color-border-strong)] p-[var(--space-8)] text-center">
          <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
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
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
      <h3 className="text-[var(--text-base)] font-medium">Code Retention</h3>
      <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
        How much agent-written code survives in the codebase
      </p>

      {/* Overall retention gauge */}
      <div className="mt-[var(--space-6)] flex items-center gap-[var(--space-6)]">
        <div className="relative h-24 w-24 shrink-0">
          <svg viewBox="0 0 100 100" className="h-full w-full -rotate-90">
            {/* Background circle */}
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke="var(--color-bg-secondary)"
              strokeWidth="8"
            />
            {/* Retention arc */}
            <circle
              cx="50"
              cy="50"
              r="42"
              fill="none"
              stroke="var(--color-accent)"
              strokeWidth="8"
              strokeDasharray={`${overallRetention * 264} 264`}
              strokeLinecap="round"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-[var(--text-xl)] font-semibold">
              {Math.round(overallRetention * 100)}%
            </span>
          </div>
        </div>

        <div className="flex-1 space-y-[var(--space-2)]">
          <div className="flex justify-between text-[var(--text-sm)]">
            <span className="text-[var(--color-text-muted)]">Lines written by agent</span>
            <span className="font-medium">{totalWritten.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-[var(--text-sm)]">
            <span className="text-[var(--color-success)]">Still in codebase</span>
            <span className="font-medium">{totalRetained.toLocaleString()}</span>
          </div>
          <div className="flex justify-between text-[var(--text-sm)]">
            <span className="text-[var(--color-accent)]">
              Overwritten by agent
            </span>
            <span className="font-medium">
              {totalOverwrittenAgent.toLocaleString()}
            </span>
          </div>
          <div className="flex justify-between text-[var(--text-sm)]">
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
      <div className="mt-[var(--space-6)] space-y-[var(--space-3)]">
        <h4 className="text-[var(--text-sm)] font-medium text-[var(--color-text-muted)]">
          Per-PR Breakdown
        </h4>
        {retention.map((r) => (
          <div
            key={r.prNumber}
            className="rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] p-[var(--space-3)]"
          >
            <div className="flex items-center justify-between">
              <a
                href={r.prUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[var(--text-sm)] font-medium text-[var(--color-accent)] hover:underline"
              >
                PR #{r.prNumber}
              </a>
              <span className="text-[var(--text-sm)] font-medium">
                {Math.round(r.retentionRate * 100)}% retained
              </span>
            </div>

            {/* Stacked bar */}
            <div className="mt-[var(--space-2)] flex h-2 overflow-hidden rounded-full bg-[var(--color-bg)]">
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
                  className="bg-[var(--color-accent)]"
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

            <div className="mt-[var(--space-1)] flex gap-[var(--space-3)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
              <span>{r.linesWritten} lines</span>
              <span>{r.filesChanged.length} files</span>
            </div>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="mt-[var(--space-4)] flex flex-wrap gap-[var(--space-4)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
        <span className="flex items-center gap-[var(--space-1)]">
          <span className="h-2 w-2 rounded-full bg-[var(--color-success)]" />
          Retained
        </span>
        <span className="flex items-center gap-[var(--space-1)]">
          <span className="h-2 w-2 rounded-full bg-[var(--color-accent)]" />
          Agent overwrite
        </span>
        <span className="flex items-center gap-[var(--space-1)]">
          <span className="h-2 w-2 rounded-full bg-[var(--color-error)]" />
          Human overwrite
        </span>
      </div>
    </div>
  );
}
