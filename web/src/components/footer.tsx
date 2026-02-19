import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
      <div className="mx-auto max-w-6xl px-[var(--space-6)] py-[var(--space-16)]">
        <div className="grid grid-cols-1 gap-[var(--space-12)] md:grid-cols-4">
          <div className="md:col-span-2">
            <p className="text-[var(--text-lg)] font-medium">LailaTov</p>
            <p className="mt-[var(--space-2)] max-w-[40ch] text-[var(--text-sm)] text-[var(--color-text-secondary)]">
              A codebase that never sleeps. Autonomous coding agents that turn
              issues into reviewed pull requests while you rest.
            </p>
          </div>

          <div>
            <p className="text-[var(--text-sm)] font-medium">Product</p>
            <ul className="mt-[var(--space-4)] space-y-[var(--space-2)]">
              <li>
                <Link
                  href="#features"
                  className="text-[var(--text-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  Features
                </Link>
              </li>
              <li>
                <Link
                  href="#pricing"
                  className="text-[var(--text-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  Pricing
                </Link>
              </li>
              <li>
                <Link
                  href="#engines"
                  className="text-[var(--text-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  Engines
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <p className="text-[var(--text-sm)] font-medium">Company</p>
            <ul className="mt-[var(--space-4)] space-y-[var(--space-2)]">
              <li>
                <a
                  href="https://github.com/korentomas/agentic-factory"
                  className="text-[var(--text-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  GitHub
                </a>
              </li>
              <li>
                <Link
                  href="/privacy"
                  className="text-[var(--text-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  Privacy
                </Link>
              </li>
              <li>
                <Link
                  href="/terms"
                  className="text-[var(--text-sm)] text-[var(--color-text-secondary)] hover:text-[var(--color-text)]"
                >
                  Terms
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-[var(--space-12)] border-t border-[var(--color-border)] pt-[var(--space-8)]">
          <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
            LailaTov. A codebase that never sleeps.
          </p>
        </div>
      </div>
    </footer>
  );
}
