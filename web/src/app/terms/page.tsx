import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Terms of Service",
};

export default function TermsPage() {
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
          Terms of Service
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Last updated: February 2026
        </p>

        <div className="mt-12 space-y-8 text-muted-foreground">
          <section>
            <h2 className="text-xl font-medium text-foreground">
              Service description
            </h2>
            <p className="mt-3">
              LailaTov is an autonomous code factory that converts GitHub issues
              into pull requests using AI agents. By using this service, you
              authorize our agents to read your repository code, create
              branches, write code, and open pull requests.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-medium text-foreground">
              Your responsibilities
            </h2>
            <p className="mt-3">
              You are responsible for reviewing all pull requests created by
              LailaTov agents before merging. Agent-generated code should be
              treated as a draft contribution, not a final product. You retain
              full ownership of your code and all agent-generated modifications.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-medium text-foreground">
              Billing
            </h2>
            <p className="mt-3">
              Subscriptions are billed monthly through Stripe. Task usage
              beyond your plan&apos;s allocation is billed at the per-task rate
              listed on the pricing page. You may cancel at any time; access
              continues until the end of your billing period.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-medium text-foreground">
              Limitations
            </h2>
            <p className="mt-3">
              LailaTov is provided as-is. We do not guarantee that
              agent-generated code will be correct, secure, or free of bugs.
              Our liability is limited to the fees paid for the service in the
              preceding 12 months.
            </p>
          </section>

          <section>
            <h2 className="text-xl font-medium text-foreground">
              Contact
            </h2>
            <p className="mt-3">
              Questions about these terms? Reach us at{" "}
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
