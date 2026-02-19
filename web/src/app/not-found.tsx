import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-[var(--color-bg)]">
      <p className="text-[var(--text-sm)] font-medium uppercase tracking-wide text-[var(--color-accent)]">
        404
      </p>
      <h1 className="mt-[var(--space-3)] text-[var(--text-3xl)] font-semibold tracking-tight">
        Page not found
      </h1>
      <p className="mt-[var(--space-3)] text-[var(--color-text-secondary)]">
        The page you&apos;re looking for doesn&apos;t exist.
      </p>
      <Link
        href="/"
        className="mt-[var(--space-8)] rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-6)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
      >
        Back to home
      </Link>
    </div>
  );
}
