import Link from "next/link";

export function Nav() {
  return (
    <nav className="fixed top-0 z-50 w-full border-b border-[var(--color-border)] bg-[var(--color-bg)]/80 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-[var(--space-6)]">
        <Link
          href="/"
          className="text-[var(--text-lg)] font-medium tracking-tight text-[var(--color-text)]"
        >
          LailaTov
        </Link>

        <div className="flex items-center gap-[var(--space-8)]">
          <Link
            href="#features"
            className="text-[var(--text-sm)] text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text)]"
          >
            Features
          </Link>
          <Link
            href="#pricing"
            className="text-[var(--text-sm)] text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text)]"
          >
            Pricing
          </Link>
          <Link
            href="#engines"
            className="text-[var(--text-sm)] text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text)]"
          >
            Engines
          </Link>
          <Link
            href="/dashboard"
            className="rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-4)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
          >
            Dashboard
          </Link>
        </div>
      </div>
    </nav>
  );
}
