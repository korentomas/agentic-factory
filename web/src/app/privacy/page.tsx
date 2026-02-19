import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <nav aria-label="Back to home" className="border-b border-[var(--color-border)]">
        <div className="mx-auto flex h-16 max-w-3xl items-center px-[var(--space-6)]">
          <Link
            href="/"
            className="text-[var(--text-lg)] font-medium tracking-tight text-[var(--color-text)]"
          >
            LailaTov
          </Link>
        </div>
      </nav>

      <main className="mx-auto max-w-3xl px-[var(--space-6)] py-[var(--space-16)]">
        <h1 className="text-[var(--text-3xl)] font-semibold tracking-tight">
          Privacy Policy
        </h1>
        <p className="mt-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text-muted)]">
          Last updated: February 2026
        </p>

        <div className="mt-[var(--space-12)] space-y-[var(--space-8)] text-[var(--color-text-secondary)]">
          <section>
            <h2 className="text-[var(--text-xl)] font-medium text-[var(--color-text)]">
              What we collect
            </h2>
            <p className="mt-[var(--space-3)]">
              When you sign in with GitHub, we receive your public profile
              information (name, email, avatar) and an access token scoped to
              the repositories you authorize. We do not read, store, or
              transmit your source code beyond what is necessary to execute
              agent tasks.
            </p>
          </section>

          <section>
            <h2 className="text-[var(--text-xl)] font-medium text-[var(--color-text)]">
              How we use it
            </h2>
            <p className="mt-[var(--space-3)]">
              Your GitHub token is used to clone repositories, create branches,
              and open pull requests on your behalf. Billing information is
              processed by Stripe and never touches our servers.
            </p>
          </section>

          <section>
            <h2 className="text-[var(--text-xl)] font-medium text-[var(--color-text)]">
              Data retention
            </h2>
            <p className="mt-[var(--space-3)]">
              Agent task metadata (task IDs, timestamps, costs) is retained for
              billing and analytics. Source code is processed in ephemeral
              workspaces that are destroyed after each task completes.
            </p>
          </section>

          <section>
            <h2 className="text-[var(--text-xl)] font-medium text-[var(--color-text)]">
              Contact
            </h2>
            <p className="mt-[var(--space-3)]">
              Questions about this policy? Reach us at{" "}
              <a
                href="mailto:hello@lailatov.dev"
                className="text-[var(--color-accent)] hover:underline"
              >
                hello@lailatov.dev
              </a>
              .
            </p>
          </section>
        </div>
      </main>
    </div>
  );
}
