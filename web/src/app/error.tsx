"use client";

export default function Error({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-bg)]">
      <p className="text-[var(--text-sm)] font-medium uppercase tracking-wide text-[var(--color-error)]">
        Error
      </p>
      <h1 className="mt-[var(--space-3)] text-[var(--text-3xl)] font-semibold tracking-tight">
        Something went wrong
      </h1>
      <p className="mt-[var(--space-3)] text-[var(--color-text-secondary)]">
        An unexpected error occurred. Please try again.
      </p>
      <button
        onClick={reset}
        className="mt-[var(--space-8)] rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-6)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
      >
        Try again
      </button>
    </div>
  );
}
