export default function Loading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[var(--color-bg)]">
      <div className="flex flex-col items-center gap-[var(--space-4)]">
        <div
          className="h-8 w-8 animate-spin rounded-full border-2 border-[var(--color-border-strong)] border-t-[var(--color-accent)]"
          role="status"
          aria-label="Loading"
        />
        <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
          Loading...
        </p>
      </div>
    </div>
  );
}
