import { Nav } from "@/components/nav";
import { BentoGrid, BentoCell } from "@/components/bento-grid";
import { PricingCard } from "@/components/pricing-card";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <>
      <Nav />

      {/* Hero */}
      <section className="flex min-h-[90vh] items-center pt-16">
        <div className="mx-auto max-w-6xl px-[var(--space-6)]">
          <div className="max-w-3xl">
            <p className="mb-[var(--space-4)] text-[var(--text-sm)] font-medium tracking-wide uppercase text-[var(--color-accent)]">
              Autonomous code factory
            </p>
            <h1 className="text-[var(--text-5xl)] font-semibold leading-[1.1] tracking-tight">
              Your codebase,
              <br />
              working while
              <br />
              you sleep.
            </h1>
            <p className="mt-[var(--space-8)] max-w-[52ch] text-[var(--text-lg)] leading-relaxed text-[var(--color-text-secondary)]">
              LailaTov connects to your GitHub repo and turns issues into
              reviewed, tested pull requests. Triage, write, review, remediate
              &mdash; all autonomous, all night long.
            </p>
            <div className="mt-[var(--space-12)] flex gap-[var(--space-4)]">
              <a
                href="/login"
                className="rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-8)] py-[var(--space-3)] text-[var(--text-base)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
              >
                Start building
              </a>
              <a
                href="https://github.com/korentomas/agentic-factory"
                className="rounded-[var(--radius-md)] border border-[var(--color-border-strong)] px-[var(--space-8)] py-[var(--space-3)] text-[var(--text-base)] text-[var(--color-text)] transition-colors hover:bg-[var(--color-bg-secondary)]"
              >
                View source
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Features — Bento Grid */}
      <section id="features" className="py-[var(--space-32)]">
        <div className="mx-auto max-w-6xl px-[var(--space-6)]">
          <h2 className="text-[var(--text-3xl)] font-semibold tracking-tight">
            The pipeline
          </h2>
          <p className="mt-[var(--space-4)] max-w-[52ch] text-[var(--color-text-secondary)]">
            Four stages, fully autonomous. Each stage uses the best engine for
            the job.
          </p>

          <BentoGrid className="mt-[var(--space-12)]">
            <BentoCell span="2">
              <p className="text-[var(--text-sm)] font-medium uppercase tracking-wide text-[var(--color-accent)]">
                01 &mdash; Triage
              </p>
              <h3 className="mt-[var(--space-3)] text-[var(--text-xl)] font-medium">
                Understands your intent
              </h3>
              <p className="mt-[var(--space-3)] text-[var(--color-text-secondary)]">
                Reads the issue, classifies risk and complexity, decides if it
                needs clarification or can proceed directly to writing code.
              </p>
            </BentoCell>

            <BentoCell>
              <p className="text-[var(--text-sm)] font-medium uppercase tracking-wide text-[var(--color-accent)]">
                02 &mdash; Write
              </p>
              <h3 className="mt-[var(--space-3)] text-[var(--text-xl)] font-medium">
                Writes the code
              </h3>
              <p className="mt-[var(--space-3)] text-[var(--color-text-secondary)]">
                Plans first for complex tasks, then writes production code
                following your repo&apos;s conventions and patterns.
              </p>
            </BentoCell>

            <BentoCell>
              <p className="text-[var(--text-sm)] font-medium uppercase tracking-wide text-[var(--color-accent)]">
                03 &mdash; Review
              </p>
              <h3 className="mt-[var(--space-3)] text-[var(--text-xl)] font-medium">
                Reviews its own work
              </h3>
              <p className="mt-[var(--space-3)] text-[var(--color-text-secondary)]">
                Runs tests, performs code review, audits against your spec.
                Blocking issues trigger automatic remediation.
              </p>
            </BentoCell>

            <BentoCell span="2">
              <p className="text-[var(--text-sm)] font-medium uppercase tracking-wide text-[var(--color-accent)]">
                04 &mdash; Learn
              </p>
              <h3 className="mt-[var(--space-3)] text-[var(--text-xl)] font-medium">
                Gets better over time
              </h3>
              <p className="mt-[var(--space-3)] text-[var(--color-text-secondary)]">
                Extracts patterns from successful PRs and anti-patterns from
                failures. Your agent improves with every task it completes.
              </p>
            </BentoCell>
          </BentoGrid>
        </div>
      </section>

      {/* Engines */}
      <section id="engines" className="bg-[var(--color-bg-secondary)] py-[var(--space-32)]">
        <div className="mx-auto max-w-6xl px-[var(--space-6)]">
          <h2 className="text-[var(--text-3xl)] font-semibold tracking-tight">
            Multi-engine architecture
          </h2>
          <p className="mt-[var(--space-4)] max-w-[52ch] text-[var(--color-text-secondary)]">
            Not locked to one AI provider. Route each pipeline stage to the best
            engine for the job.
          </p>

          <div className="mt-[var(--space-12)] overflow-x-auto">
            <table className="w-full text-left text-[var(--text-sm)]">
              <thead>
                <tr className="border-b border-[var(--color-border-strong)]">
                  <th className="pb-[var(--space-3)] font-medium">Engine</th>
                  <th className="pb-[var(--space-3)] font-medium">Models</th>
                  <th className="pb-[var(--space-3)] font-medium">Best for</th>
                  <th className="pb-[var(--space-3)] font-medium">Tier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-border)]">
                {[
                  ["Claude Code", "Opus, Sonnet, Haiku", "Complex coding, deep reasoning", "Team+"],
                  ["Codex", "GPT-4.1, o3", "OpenAI ecosystem, sandboxed execution", "Team+"],
                  ["Gemini CLI", "Gemini 2.5 Flash/Pro", "Free tier, fast iteration", "Starter+"],
                  ["Aider", "Any (via LiteLLM)", "Model experiments, fallback", "All"],
                  ["Kimi CLI", "Kimi K2, K2.5", "Cost-effective, multilingual", "Starter+"],
                  ["SWE-agent", "Any", "Research, benchmarking", "Enterprise"],
                ].map(([engine, models, best, tier]) => (
                  <tr key={engine} className="text-[var(--color-text-secondary)]">
                    <td className="py-[var(--space-3)] font-medium text-[var(--color-text)]">
                      {engine}
                    </td>
                    <td className="py-[var(--space-3)]">{models}</td>
                    <td className="py-[var(--space-3)]">{best}</td>
                    <td className="py-[var(--space-3)]">{tier}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-[var(--space-32)]">
        <div className="mx-auto max-w-6xl px-[var(--space-6)]">
          <h2 className="text-[var(--text-3xl)] font-semibold tracking-tight">
            Simple, transparent pricing
          </h2>
          <p className="mt-[var(--space-4)] max-w-[52ch] text-[var(--color-text-secondary)]">
            Pay for the tasks your agents complete. Each task is one
            issue-to-PR pipeline run.
          </p>

          <div className="mt-[var(--space-12)] grid grid-cols-1 gap-[var(--space-6)] md:grid-cols-3">
            <PricingCard
              name="Starter"
              price="$49"
              period="/month"
              description="For individual developers getting started."
              features={[
                "30 tasks per month",
                "3 repositories",
                "Budget engines (Gemini, DeepSeek)",
                "Community support",
                "$2.00 per additional task",
              ]}
              cta="Start free trial"
              href="/login?plan=starter"
            />
            <PricingCard
              name="Team"
              price="$249"
              period="/month"
              description="For teams that ship fast."
              highlighted
              features={[
                "150 tasks per month",
                "10 repositories",
                "Standard + Budget engines",
                "Claude Sonnet, GPT-4.1",
                "Priority support",
                "BYOK option ($99/mo)",
                "$1.75 per additional task",
              ]}
              cta="Start free trial"
              href="/login?plan=team"
            />
            <PricingCard
              name="Enterprise"
              price="$999"
              period="/month"
              description="For organizations at scale."
              features={[
                "500 tasks per month",
                "Unlimited repositories",
                "All engines + custom routing",
                "Claude Opus, o3, Gemini Pro",
                "Dedicated support",
                "BYOK option ($399/mo)",
                "$1.50 per additional task",
              ]}
              cta="Contact sales"
              href="mailto:hello@lailatov.dev?subject=Enterprise"
            />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="bg-[var(--color-accent)] py-[var(--space-24)]">
        <div className="mx-auto max-w-6xl px-[var(--space-6)] text-center">
          <h2 className="text-[var(--text-3xl)] font-semibold tracking-tight text-[var(--color-text-inverse)]">
            Ship code while you sleep
          </h2>
          <p className="mx-auto mt-[var(--space-4)] max-w-[44ch] text-[var(--color-text-inverse)]/70">
            Connect your repo in 2 minutes. Your first PR ships tonight.
          </p>
          <a
            href="/login"
            className="mt-[var(--space-8)] inline-block rounded-[var(--radius-md)] bg-[var(--color-bg-surface)] px-[var(--space-8)] py-[var(--space-3)] text-[var(--text-base)] font-medium text-[var(--color-accent)] transition-colors hover:bg-[var(--color-bg)]"
          >
            Get started free
          </a>
        </div>
      </section>

      <Footer />
    </>
  );
}
