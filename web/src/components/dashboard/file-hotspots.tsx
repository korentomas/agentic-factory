import type { FileHotspot } from "@/lib/data/types";

export function FileHotspotsPanel({
  hotspots,
}: {
  hotspots: FileHotspot[];
}) {
  if (hotspots.length === 0) {
    return null;
  }

  const maxAppearances = Math.max(...hotspots.map((h) => h.appearances), 1);

  return (
    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
      <h3 className="text-[var(--text-base)] font-medium">File Hotspots</h3>
      <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
        Most frequently changed files across agent tasks
      </p>

      <div className="mt-[var(--space-6)] space-y-[var(--space-2)]">
        {hotspots.slice(0, 10).map((hotspot) => (
          <div
            key={hotspot.path}
            className="flex items-center gap-[var(--space-3)]"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-[var(--text-xs)]">
                {hotspot.path}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-[var(--space-2)]">
              <div className="flex h-2 w-20 overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
                <div
                  className="bg-[var(--color-success)]"
                  style={{
                    width: `${(hotspot.inSuccessful / maxAppearances) * 100}%`,
                  }}
                />
                <div
                  className="bg-[var(--color-error)]"
                  style={{
                    width: `${(hotspot.inFailed / maxAppearances) * 100}%`,
                  }}
                />
              </div>
              <span className="w-6 text-right text-[var(--text-xs)] text-[var(--color-text-muted)]">
                {hotspot.appearances}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
