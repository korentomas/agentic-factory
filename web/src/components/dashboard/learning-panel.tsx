import type { LearningStats } from "@/lib/data/types";

export function LearningPanel({ learning }: { learning: LearningStats }) {
  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
      <div className="flex items-start justify-between">
        <div>
          <h3 className="text-[var(--text-base)] font-medium">
            Self-Learning Pipeline
          </h3>
          <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
            Patterns extracted from agent outcomes
          </p>
        </div>
        <div
          className={`rounded-full px-[var(--space-3)] py-[var(--space-1)] text-[var(--text-xs)] font-medium ${
            learning.nextExtractionEligible
              ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
              : "bg-[var(--color-bg-secondary)] text-[var(--color-text-muted)]"
          }`}
        >
          {learning.nextExtractionEligible
            ? "Extraction ready"
            : `Need ${3 - learning.totalOutcomes} more outcomes`}
        </div>
      </div>

      {/* Stats row */}
      <div className="mt-[var(--space-6)] grid grid-cols-3 gap-[var(--space-4)]">
        <div className="text-center">
          <p className="text-[var(--text-2xl)] font-semibold">
            {learning.totalOutcomes}
          </p>
          <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
            Total outcomes
          </p>
        </div>
        <div className="text-center">
          <p className="text-[var(--text-2xl)] font-semibold text-[var(--color-success)]">
            {learning.patternsDiscovered}
          </p>
          <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
            Patterns learned
          </p>
        </div>
        <div className="text-center">
          <p className="text-[var(--text-2xl)] font-semibold text-[var(--color-error)]">
            {learning.antiPatternsDiscovered}
          </p>
          <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
            Anti-patterns
          </p>
        </div>
      </div>

      {/* Extraction timeline */}
      <div className="mt-[var(--space-6)]">
        <div className="flex items-center gap-[var(--space-3)]">
          <div className="flex flex-1 items-center gap-[var(--space-2)]">
            {/* Progress dots for learning milestones */}
            {[1, 2, 3, 5, 10, 20, 50].map((milestone) => (
              <div key={milestone} className="flex flex-col items-center">
                <div
                  className={`h-3 w-3 rounded-full border-2 ${
                    learning.totalOutcomes >= milestone
                      ? "border-[var(--color-accent)] bg-[var(--color-accent)]"
                      : "border-[var(--color-border-strong)] bg-transparent"
                  }`}
                />
                <span className="mt-[var(--space-1)] text-[10px] text-[var(--color-text-muted)]">
                  {milestone}
                </span>
              </div>
            ))}
          </div>
        </div>
        <p className="mt-[var(--space-2)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
          Outcomes processed — more data improves pattern confidence
        </p>
      </div>

      {/* Discovered patterns */}
      {learning.patterns.length > 0 && (
        <div className="mt-[var(--space-6)] space-y-[var(--space-3)]">
          <h4 className="text-[var(--text-sm)] font-medium text-[var(--color-text-muted)]">
            Active Rules
          </h4>
          {learning.patterns.map((pattern, i) => (
            <div
              key={i}
              className={`rounded-[var(--radius-md)] border p-[var(--space-4)] ${
                pattern.kind === "pattern"
                  ? "border-[var(--color-success)]/20 bg-[var(--color-success)]/5"
                  : "border-[var(--color-error)]/20 bg-[var(--color-error)]/5"
              }`}
            >
              <div className="flex items-start justify-between">
                <p className="text-[var(--text-sm)]">{pattern.description}</p>
                <span
                  className={`ml-[var(--space-2)] shrink-0 rounded-full px-[var(--space-2)] py-0.5 text-[var(--text-xs)] font-medium ${
                    pattern.kind === "pattern"
                      ? "bg-[var(--color-success)]/10 text-[var(--color-success)]"
                      : "bg-[var(--color-error)]/10 text-[var(--color-error)]"
                  }`}
                >
                  {pattern.kind}
                </span>
              </div>
              <div className="mt-[var(--space-2)] flex gap-[var(--space-3)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
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
        <div className="mt-[var(--space-6)] rounded-[var(--radius-md)] border border-dashed border-[var(--color-border-strong)] p-[var(--space-6)] text-center">
          <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
            No patterns extracted yet. The agent learns from completed tasks — patterns emerge
            after 3+ successful PRs touching the same areas.
          </p>
        </div>
      )}

      {learning.lastExtractionDate && (
        <p className="mt-[var(--space-4)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
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
