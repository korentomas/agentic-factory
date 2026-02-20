import type { LearningStats } from "@/lib/data/types";

export function LearningPanel({ learning }: { learning: LearningStats }) {
  return (
    <div className="rounded-lg border border-border bg-card p-6">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-base font-medium">
            Self-Learning Pipeline
          </h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Patterns extracted from agent outcomes
          </p>
        </div>
        <div
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            learning.nextExtractionEligible
              ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
              : "bg-muted text-muted-foreground"
          }`}
        >
          {learning.nextExtractionEligible
            ? "Extraction ready"
            : `Need ${3 - learning.totalOutcomes} more outcomes`}
        </div>
      </div>

      {/* Stats row */}
      <div className="mt-6 grid grid-cols-3 gap-4">
        <div className="text-center">
          <p className="text-2xl font-semibold">
            {learning.totalOutcomes}
          </p>
          <p className="text-xs text-muted-foreground">
            Total outcomes
          </p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-semibold text-[var(--color-success)]">
            {learning.patternsDiscovered}
          </p>
          <p className="text-xs text-muted-foreground">
            Patterns learned
          </p>
        </div>
        <div className="text-center">
          <p className="text-2xl font-semibold text-[var(--color-error)]">
            {learning.antiPatternsDiscovered}
          </p>
          <p className="text-xs text-muted-foreground">
            Anti-patterns
          </p>
        </div>
      </div>

      {/* Extraction timeline */}
      <div className="mt-6">
        <div className="flex items-center gap-3">
          <div className="flex flex-1 items-center gap-2">
            {/* Progress dots for learning milestones */}
            {[1, 2, 3, 5, 10, 20, 50].map((milestone) => (
              <div key={milestone} className="flex flex-col items-center">
                <div
                  className={`h-3 w-3 rounded-full border-2 ${
                    learning.totalOutcomes >= milestone
                      ? "border-primary bg-primary"
                      : "border-border bg-transparent"
                  }`}
                />
                <span className="mt-1 text-[10px] text-muted-foreground">
                  {milestone}
                </span>
              </div>
            ))}
          </div>
        </div>
        <p className="mt-2 text-xs text-muted-foreground">
          Outcomes processed — more data improves pattern confidence
        </p>
      </div>

      {/* Discovered patterns */}
      {learning.patterns.length > 0 && (
        <div className="mt-6 space-y-3">
          <h4 className="text-sm font-medium text-muted-foreground">
            Active Rules
          </h4>
          {learning.patterns.map((pattern, i) => (
            <div
              key={i}
              className={`rounded-md border p-4 ${
                pattern.kind === "pattern"
                  ? "border-[var(--color-success)]/20 bg-[var(--color-success)]/5"
                  : "border-[var(--color-error)]/20 bg-[var(--color-error)]/5"
              }`}
            >
              <div className="flex items-start justify-between">
                <p className="text-sm">{pattern.description}</p>
                <span
                  className={`ml-2 shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
                    pattern.kind === "pattern"
                      ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                      : "bg-[var(--color-error)]/10 text-[var(--color-error)]"
                  }`}
                >
                  {pattern.kind}
                </span>
              </div>
              <div className="mt-2 flex gap-3 text-xs text-muted-foreground">
                <span>Evidence: {pattern.evidenceCount} runs</span>
                <span>
                  Confidence: {Math.round(pattern.confidence * 100)}%
                </span>
              </div>
            </div>
          ))}
        </div>
      )}

      {learning.patterns.length === 0 && (
        <div className="mt-6 rounded-md border border-dashed border-border p-6 text-center">
          <p className="text-sm text-muted-foreground">
            No patterns extracted yet. The agent learns from completed tasks — patterns emerge
            after 3+ successful PRs touching the same areas.
          </p>
        </div>
      )}

      {learning.lastExtractionDate && (
        <p className="mt-4 text-xs text-muted-foreground">
          Last extraction:{" "}
          {new Date(learning.lastExtractionDate).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            year: "numeric",
          })}
        </p>
      )}
    </div>
  );
}
