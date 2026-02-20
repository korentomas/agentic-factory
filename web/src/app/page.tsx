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
        <div className="mx-auto max-w-6xl px-6">
          <div className="max-w-3xl">
            <p className="mb-4 text-sm font-medium tracking-wide uppercase text-primary">
              Autonomous code factory
            </p>
            <h1 className="text-5xl font-semibold leading-[1.1] tracking-tight">
              Your codebase,
              <br />
              working while
              <br />
              you sleep.
            </h1>
            <p className="mt-8 max-w-[52ch] text-lg leading-relaxed text-muted-foreground">
              LailaTov connects to your GitHub repo and turns issues into
              reviewed, tested pull requests. Triage, write, review, remediate
              &mdash; all autonomous, all night long.
            </p>
            <div className="mt-12 flex flex-col gap-4 sm:flex-row">
              <a
                href="/login"
                className="rounded-md bg-primary px-8 py-3 text-center text-base font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Start building
              </a>
              <a
                href="https://github.com/korentomas/agentic-factory"
                className="rounded-md border border-border px-8 py-3 text-center text-base text-foreground transition-colors hover:bg-muted"
              >
                View source
              </a>
            </div>
          </div>
        </div>
      </section>

      {/* Features — Bento Grid */}
      <section id="features" className="py-32">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-3xl font-semibold tracking-tight">
            The pipeline
          </h2>
          <p className="mt-4 max-w-[52ch] text-muted-foreground">
            Four stages, fully autonomous. Each stage uses the best engine for
            the job.
          </p>

          <BentoGrid className="mt-12">
            <BentoCell span="2">
              <p className="text-sm font-medium uppercase tracking-wide text-primary">
                01 &mdash; Triage
              </p>
              <h3 className="mt-3 text-xl font-medium">
                Understands your intent
              </h3>
              <p className="mt-3 text-muted-foreground">
                Reads the issue, classifies risk and complexity, decides if it
                needs clarification or can proceed directly to writing code.
              </p>
            </BentoCell>

            <BentoCell>
              <p className="text-sm font-medium uppercase tracking-wide text-primary">
                02 &mdash; Write
              </p>
              <h3 className="mt-3 text-xl font-medium">
                Writes the code
              </h3>
              <p className="mt-3 text-muted-foreground">
                Plans first for complex tasks, then writes production code
                following your repo&apos;s conventions and patterns.
              </p>
            </BentoCell>

            <BentoCell>
              <p className="text-sm font-medium uppercase tracking-wide text-primary">
                03 &mdash; Review
              </p>
              <h3 className="mt-3 text-xl font-medium">
                Reviews its own work
              </h3>
              <p className="mt-3 text-muted-foreground">
                Runs tests, performs code review, audits against your spec.
                Blocking issues trigger automatic remediation.
              </p>
            </BentoCell>

            <BentoCell span="2">
              <p className="text-sm font-medium uppercase tracking-wide text-primary">
                04 &mdash; Learn
              </p>
              <h3 className="mt-3 text-xl font-medium">
                Gets better over time
              </h3>
              <p className="mt-3 text-muted-foreground">
                Extracts patterns from successful PRs and anti-patterns from
                failures. Your agent improves with every task it completes.
              </p>
            </BentoCell>
          </BentoGrid>
        </div>
      </section>

      {/* Engines */}
      <section id="engines" className="bg-muted py-32">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-3xl font-semibold tracking-tight">
            Multi-engine architecture
          </h2>
          <p className="mt-4 max-w-[52ch] text-muted-foreground">
            Not locked to one AI provider. Route each pipeline stage to the best
            engine for the job.
          </p>

          <div className="mt-12 overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border">
                  <th className="pb-3 font-medium">Engine</th>
                  <th className="pb-3 font-medium">Models</th>
                  <th className="pb-3 font-medium">Best for</th>
                  <th className="pb-3 font-medium">Tier</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {[
                  ["Claude Code", "Opus, Sonnet, Haiku", "Complex coding, deep reasoning", "Team+"],
                  ["Codex", "GPT-4.1, o3", "OpenAI ecosystem, sandboxed execution", "Team+"],
                  ["Gemini CLI", "Gemini 2.5 Flash/Pro", "Free tier, fast iteration", "Starter+"],
                  ["Aider", "Any (via LiteLLM)", "Model experiments, fallback", "All"],
                  ["Kimi CLI", "Kimi K2, K2.5", "Cost-effective, multilingual", "Starter+"],
                  ["SWE-agent", "Any", "Research, benchmarking", "Enterprise"],
                ].map(([engine, models, best, tier]) => (
                  <tr key={engine} className="text-muted-foreground">
                    <td className="py-3 font-medium text-foreground">
                      {engine}
                    </td>
                    <td className="py-3">{models}</td>
                    <td className="py-3">{best}</td>
                    <td className="py-3">{tier}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" className="py-32">
        <div className="mx-auto max-w-6xl px-6">
          <h2 className="text-3xl font-semibold tracking-tight">
            Simple, transparent pricing
          </h2>
          <p className="mt-4 max-w-[52ch] text-muted-foreground">
            Pay for the tasks your agents complete. Each task is one
            issue-to-PR pipeline run.
          </p>

          <div className="mt-12 grid grid-cols-1 gap-6 md:grid-cols-3">
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
              planId="starter"
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
              planId="team"
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
      <section className="bg-primary py-24">
        <div className="mx-auto max-w-6xl px-6 text-center">
          <h2 className="text-3xl font-semibold tracking-tight text-primary-foreground">
            Ship code while you sleep
          </h2>
          <p className="mx-auto mt-4 max-w-[44ch] text-primary-foreground/70">
            Connect your repo in 2 minutes. Your first PR ships tonight.
          </p>
          <a
            href="/login"
            className="mt-8 inline-block rounded-md bg-card px-8 py-3 text-base font-medium text-primary transition-colors hover:bg-background"
          >
            Get started free
          </a>
        </div>
      </section>

      <Footer />
    </>
  );
}
