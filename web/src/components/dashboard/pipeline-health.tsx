import type { CheckHealth, RiskBreakdown } from "@/lib/data/types";

function PassRateBar({
  passRate,
  label,
}: {
  passRate: number;
  label: string;
}) {
  const pct = Math.round(passRate * 100);
  const color =
    pct >= 90
      ? "bg-[var(--color-success)]"
      : pct >= 70
        ? "bg-[var(--color-warning)]"
        : "bg-[var(--color-error)]";

  return (
    <div>
      <div className="flex items-center justify-between text-[var(--text-sm)]">
        <span>{label}</span>
        <span className="font-medium">{pct}%</span>
      </div>
      <div className="mt-[var(--space-2)] h-2 overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
        <div
          className={`h-full rounded-full transition-all ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export function PipelineHealth({
  checks,
  risks,
}: {
  checks: CheckHealth[];
  risks: RiskBreakdown[];
}) {
  return (
    <div className="grid grid-cols-1 gap-[var(--space-6)] lg:grid-cols-2">
      {/* Check pass rates */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
        <h3 className="text-[var(--text-base)] font-medium">
          Pipeline Checks
        </h3>
        <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
          Pass rates across all runs
        </p>

        <div className="mt-[var(--space-6)] space-y-[var(--space-4)]">
          {checks.map((check) => (
            <div key={check.name}>
              <PassRateBar passRate={check.passRate} label={check.name} />
              <div className="mt-[var(--space-1)] flex gap-[var(--space-3)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
                <span>{check.passed} passed</span>
                <span>{check.failed} failed</span>
                {check.skipped > 0 && <span>{check.skipped} skipped</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Risk tier breakdown */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
        <h3 className="text-[var(--text-base)] font-medium">
          Risk Tiers
        </h3>
        <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
          Success rates by risk classification
        </p>

        <div className="mt-[var(--space-6)] space-y-[var(--space-4)]">
          {risks.map((risk) => {
            const tierColors: Record<string, string> = {
              high: "text-[var(--color-error)]",
              medium: "text-[var(--color-warning)]",
              low: "text-[var(--color-text-muted)]",
            };

            return (
              <div
                key={risk.tier}
                className="flex items-center justify-between rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] p-[var(--space-4)]"
              >
                <div>
                  <span
                    className={`text-[var(--text-sm)] font-medium uppercase ${tierColors[risk.tier]}`}
                  >
                    {risk.tier}
                  </span>
                  <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
                    {risk.count} tasks
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-[var(--text-2xl)] font-semibold">
                    {Math.round(risk.successRate * 100)}%
                  </p>
                  <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
                    {risk.successCount}/{risk.count} shipped
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
