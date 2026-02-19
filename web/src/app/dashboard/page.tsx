import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { auth, signOut } from "@/lib/auth";
import { loadDashboardData } from "@/lib/data";
import { StatsCards } from "@/components/dashboard/stats-cards";
import { PRTable } from "@/components/dashboard/pr-table";
import { EngineBreakdownPanel } from "@/components/dashboard/engine-breakdown";
import { PipelineHealth } from "@/components/dashboard/pipeline-health";
import { LearningPanel } from "@/components/dashboard/learning-panel";
import { CodeRetentionPanel } from "@/components/dashboard/code-retention";
import { FileHotspotsPanel } from "@/components/dashboard/file-hotspots";
import { ConnectRepo } from "@/components/dashboard/connect-repo";
import { DashboardTabs } from "@/components/dashboard/dashboard-tabs";
import { ChatPanel } from "@/components/dashboard/chat-panel";
import { ThemeToggle } from "@/components/theme-toggle";

export const metadata: Metadata = {
  title: "Dashboard",
};

export const dynamic = "force-dynamic";

export default async function Dashboard() {
  const session = await auth();

  if (!session?.user) {
    redirect("/login");
  }

  const user = session.user;
  const accessToken = session.accessToken;
  const data = await loadDashboardData(accessToken);
  const hasData = data.outcomes.length > 0;

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Dashboard nav */}
      <nav
        aria-label="Dashboard navigation"
        className="border-b border-[var(--color-border)] bg-[var(--color-bg-surface)]"
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-[var(--space-6)]">
          <Link
            href="/"
            className="text-[var(--text-lg)] font-medium tracking-tight text-[var(--color-text)]"
          >
            LailaTov
          </Link>

          <div className="flex items-center gap-[var(--space-4)]">
            <ThemeToggle />
            <span className="text-[var(--text-sm)] text-[var(--color-text-secondary)]">
              {user.name || user.email}
            </span>
            {user.image && (
              <Image
                src={user.image}
                alt={`${user.name || "User"} avatar`}
                width={32}
                height={32}
                className="rounded-full"
              />
            )}
            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/" });
              }}
            >
              <button
                type="submit"
                className="text-[var(--text-sm)] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-[var(--space-6)] py-[var(--space-8)]">
        {/* Header */}
        <div className="mb-[var(--space-8)] flex items-center justify-between">
          <div>
            <h1 className="text-[var(--text-3xl)] font-semibold tracking-tight">
              Welcome back, {user.name?.split(" ")[0] || "developer"}
            </h1>
            <p className="mt-[var(--space-2)] text-[var(--color-text-secondary)]">
              Your autonomous code factory is{" "}
              {hasData ? "running" : "ready to start"}.
            </p>
          </div>
          <Link
            href="/dashboard/tasks"
            className="rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-4)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
          >
            Open Tasks
          </Link>
        </div>

        {/* Stats overview */}
        <section className="mb-[var(--space-8)]">
          <StatsCards stats={data.stats} />
        </section>

        {hasData ? (
          <Suspense fallback={null}>
            <DashboardTabs>
              {{
                overview: (
                  <>
                    <section className="mb-[var(--space-8)]">
                      <h2 className="mb-[var(--space-4)] text-[var(--text-xl)] font-medium">
                        Pipeline Health
                      </h2>
                      <PipelineHealth checks={data.checks} risks={data.risks} />
                    </section>
                    <section className="mb-[var(--space-8)]">
                      <h2 className="mb-[var(--space-4)] text-[var(--text-xl)] font-medium">
                        Code Quality
                      </h2>
                      <div className="grid grid-cols-1 gap-[var(--space-6)] lg:grid-cols-2">
                        <CodeRetentionPanel retention={data.codeRetention} />
                        <FileHotspotsPanel hotspots={data.fileHotspots} />
                      </div>
                    </section>
                  </>
                ),
                prs: (
                  <section>
                    <div className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]">
                      <PRTable prs={data.prs} />
                    </div>
                  </section>
                ),
                engines: (
                  <section>
                    <EngineBreakdownPanel
                      engines={data.engines}
                      models={data.models}
                    />
                  </section>
                ),
                learning: (
                  <section>
                    <LearningPanel learning={data.learning} />
                  </section>
                ),
                chat: (
                  <section>
                    <ChatPanel />
                  </section>
                ),
              }}
            </DashboardTabs>
          </Suspense>
        ) : (
          <>
            <section className="mb-[var(--space-8)]">
              <ConnectRepo />
            </section>
            <section>
              <h2 className="text-[var(--text-xl)] font-medium">
                Recent activity
              </h2>
              <div className="mt-[var(--space-6)] rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-strong)] p-[var(--space-12)] text-center">
                <p className="text-[var(--color-text-muted)]">
                  No tasks yet. Label a GitHub issue with{" "}
                  <code className="rounded bg-[var(--color-bg-secondary)] px-[var(--space-2)] py-[var(--space-1)] font-mono text-[var(--text-sm)]">
                    ai-agent
                  </code>{" "}
                  to get started.
                </p>
              </div>
            </section>
          </>
        )}
      </main>
    </div>
  );
}
