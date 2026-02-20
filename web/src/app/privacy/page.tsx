import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Privacy Policy",
};

export default function PrivacyPage() {
  return (
    <div className="min-h-screen bg-background">
      <nav aria-label="Back to home" className="border-b border-border">
        <div className="mx-auto flex h-16 max-w-3xl items-center px-6">
          <Link
            href="/"
            className="text-lg font-medium tracking-tight text-foreground"
          >
            LailaTov
          </Link>
        </div>
      </nav>

      <main className="mx-auto max-w-3xl px-6 py-16">
        <h1 className="text-3xl font-semibold tracking-tight">
          Privacy Policy
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Last updated: February 2026
        </p>

        <div className="mt-12 space-y-8 text-muted-foreground">
          <section>
            <h2 className="text-xl font-medium text-foreground">
              What we collect
            </h2>
            <p className="mt-3">
              When you sign in with GitHub, we receive your public profile
              information (name, email, avatar) and an access token scoped to
              the repositories you authorize. We do not read, store, or
              transmit your source code beyond what is necessary to execute
              agent tasks.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-medium text-foreground">
              How we use it
            </h2>
            <p className="mt-3">
              Your GitHub token is used to clone repositories, create branches,
              and open pull requests on your behalf. Billing information is
              processed by Stripe and never touches our servers.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-medium text-foreground">
              Data retention
            </h2>
            <p className="mt-3">
              Agent task metadata (task IDs, timestamps, costs) is retained for
              billing and analytics. Source code is processed in ephemeral
              workspaces that are destroyed after each task completes.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-medium text-foreground">
              Contact
            </h2>
            <p className="mt-3">
              Questions about this policy? Reach us at{" "}
              <a
                href="mailto:hello@lailatov.dev"
                className="text-primary hover:underline"
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
