import type { EngineBreakdown, ModelBreakdown } from "@/lib/data/types";

function BarSegment({
  value,
  max,
  color,
}: {
  value: number;
  max: number;
  color: string;
}) {
  const width = max > 0 ? (value / max) * 100 : 0;
  return (
    <div
      className={`h-2 rounded-full ${color}`}
      style={{ width: `${Math.max(width, 2)}%` }}
    />
  );
}

export function EngineBreakdownPanel({
  engines,
  models,
}: {
  engines: EngineBreakdown[];
  models: ModelBreakdown[];
}) {
  const maxEngineCount = Math.max(...engines.map((e) => e.count), 1);
  const maxModelCount = Math.max(...models.map((m) => m.count), 1);

  return (
    <div className="grid grid-cols-1 gap-[var(--space-6)] lg:grid-cols-2">
      {/* Engines */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
        <h3 className="text-[var(--text-base)] font-medium">
          Engines
        </h3>
        <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
          Tasks by coding engine
        </p>

        <div className="mt-[var(--space-6)] space-y-[var(--space-4)]">
          {engines.length === 0 ? (
            <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
              No engine data yet
            </p>
          ) : (
            engines.map((engine) => (
              <div key={engine.engine}>
                <div className="flex items-center justify-between text-[var(--text-sm)]">
                  <span className="font-medium">{engine.engine}</span>
                  <span className="text-[var(--color-text-muted)]">
                    {engine.count} tasks &middot;{" "}
                    {Math.round(engine.successRate * 100)}% success
                  </span>
                </div>
                <div className="mt-[var(--space-2)] flex gap-[var(--space-1)]">
                  <BarSegment
                    value={engine.successCount}
                    max={maxEngineCount}
                    color="bg-[var(--color-success)]"
                  />
                  <BarSegment
                    value={engine.failureCount}
                    max={maxEngineCount}
                    color="bg-[var(--color-error)]"
                  />
                </div>
                {engine.avgCost > 0 && (
                  <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
                    Avg cost: ${engine.avgCost.toFixed(2)} &middot; Avg duration:{" "}
                    {Math.round(engine.avgDuration / 1000)}s
                  </p>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Models */}
      <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
        <h3 className="text-[var(--text-base)] font-medium">
          Models
        </h3>
        <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
          Tasks by AI model
        </p>

        <div className="mt-[var(--space-6)] space-y-[var(--space-4)]">
          {models.length === 0 ? (
            <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
              No model data yet
            </p>
          ) : (
            models.map((model) => (
              <div key={model.model}>
                <div className="flex items-center justify-between text-[var(--text-sm)]">
                  <span className="font-mono text-[var(--text-xs)] font-medium">
                    {model.model}
                  </span>
                  <span className="text-[var(--color-text-muted)]">
                    {model.count} tasks &middot;{" "}
                    {Math.round(model.successRate * 100)}% success
                  </span>
                </div>
                <div className="mt-[var(--space-2)] flex gap-[var(--space-1)]">
                  <BarSegment
                    value={model.successCount}
                    max={maxModelCount}
                    color="bg-[var(--color-accent)]"
                  />
                  <BarSegment
                    value={model.failureCount}
                    max={maxModelCount}
                    color="bg-[var(--color-error)]"
                  />
                </div>
                <div className="mt-[var(--space-1)] flex gap-[var(--space-2)]">
                  {model.stages.map((stage) => (
                    <span
                      key={stage}
                      className="rounded bg-[var(--color-bg-secondary)] px-[var(--space-1)] py-0.5 text-[var(--text-xs)] text-[var(--color-text-muted)]"
                    >
                      {stage}
                    </span>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
