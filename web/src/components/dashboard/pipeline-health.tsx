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
      <div className="flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="font-medium">{pct}%</span>
      </div>
      <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
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
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      {/* Check pass rates */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="text-base font-medium">
          Pipeline Checks
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Pass rates across all runs
        </p>

        <div className="mt-6 space-y-4">
          {checks.map((check) => (
            <div key={check.name}>
              <PassRateBar passRate={check.passRate} label={check.name} />
              <div className="mt-1 flex gap-3 text-xs text-muted-foreground">
                <span>{check.passed} passed</span>
                <span>{check.failed} failed</span>
                {check.skipped > 0 && <span>{check.skipped} skipped</span>}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Risk tier breakdown */}
      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="text-base font-medium">
          Risk Tiers
        </h3>
        <p className="mt-1 text-xs text-muted-foreground">
          Success rates by risk classification
        </p>

        <div className="mt-6 space-y-4">
          {risks.map((risk) => {
            const tierColors: Record<string, string> = {
              high: "text-[var(--color-error)]",
              medium: "text-[var(--color-warning)]",
              low: "text-muted-foreground",
            };

            return (
              <div
                key={risk.tier}
                className="flex items-center justify-between rounded-md bg-muted p-4"
              >
                <div>
                  <span
                    className={`text-sm font-medium uppercase ${tierColors[risk.tier]}`}
                  >
                    {risk.tier}
                  </span>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {risk.count} tasks
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-2xl font-semibold">
                    {Math.round(risk.successRate * 100)}%
                  </p>
                  <p className="text-xs text-muted-foreground">
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
