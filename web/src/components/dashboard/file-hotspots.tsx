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
    <div className="rounded-lg border border-border bg-card p-6">
      <h3 className="text-base font-medium">File Hotspots</h3>
      <p className="mt-1 text-xs text-muted-foreground">
        Most frequently changed files across agent tasks
      </p>

      <div className="mt-6 space-y-2">
        {hotspots.slice(0, 10).map((hotspot) => (
          <div
            key={hotspot.path}
            className="flex items-center gap-3"
          >
            <div className="min-w-0 flex-1">
              <p className="truncate font-mono text-xs">
                {hotspot.path}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              <div className="flex h-2 w-20 overflow-hidden rounded-full bg-muted">
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
              <span className="w-6 text-right text-xs text-muted-foreground">
                {hotspot.appearances}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
