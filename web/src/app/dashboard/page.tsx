import type { Metadata } from "next";
import { redirect } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Suspense } from "react";
import { auth, signOut } from "@/lib/auth";
import { loadDashboardData } from "@/lib/data";
import { getRepositories } from "@/lib/db/queries";
import { syncGitHubRepos } from "@/lib/github/sync-repos";
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

async function checkRunnerHealth(): Promise<boolean> {
  const runnerUrl = process.env.RUNNER_API_URL;
  if (!runnerUrl) return false;
  try {
    const res = await fetch(`${runnerUrl}/health`, {
      headers: { Authorization: `Bearer ${process.env.RUNNER_API_KEY || ""}` },
      next: { revalidate: 0 },
      signal: AbortSignal.timeout(5000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export default async function Dashboard() {
  const session = await auth();

  if (!session?.user) {
    redirect("/login");
  }

  const user = session.user;
  const accessToken = session.accessToken;

  // Sync repos from GitHub App installations
  let syncError: string | undefined;
  if (session.user.id) {
    try {
      const result = await syncGitHubRepos(session.user.id, accessToken);
      syncError = result.error;
    } catch (err) {
      console.error("[dashboard] syncGitHubRepos threw:", err);
      syncError = "sync_exception";
    }
  }

  // Load dashboard data and check setup status in parallel
  const [data, repos, runnerOk] = await Promise.all([
    loadDashboardData(accessToken),
    session.user.id ? getRepositories(session.user.id) : Promise.resolve([]),
    checkRunnerHealth(),
  ]);
  const hasData = data.outcomes.length > 0;

  return (
    <div className="min-h-screen bg-background">
      {/* Dashboard nav */}
      <nav
        aria-label="Dashboard navigation"
        className="border-b border-border bg-card"
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <Link
            href="/"
            className="text-lg font-medium tracking-tight text-foreground"
          >
            LailaTov
          </Link>

          <div className="flex items-center gap-4">
            <ThemeToggle />
            <span className="text-sm text-muted-foreground">
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
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {/* Header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">
              Welcome back, {user.name?.split(" ")[0] || "developer"}
            </h1>
            <p className="mt-2 text-muted-foreground">
              Your autonomous code factory is{" "}
              {hasData ? "running" : "ready to start"}.
            </p>
          </div>
          <Link
            href="/chat"
            className="rounded-md bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Open Tasks
          </Link>
        </div>

        {/* Stats overview */}
        <section className="mb-8">
          <StatsCards stats={data.stats} />
        </section>

        <Suspense fallback={null}>
          <DashboardTabs>
            {{
              overview: hasData ? (
                <>
                  <section className="mb-8">
                    <h2 className="mb-4 text-xl font-medium">
                      Pipeline Health
                    </h2>
                    <PipelineHealth checks={data.checks} risks={data.risks} />
                  </section>
                  <section className="mb-8">
                    <h2 className="mb-4 text-xl font-medium">
                      Code Quality
                    </h2>
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                      <CodeRetentionPanel retention={data.codeRetention} />
                      <FileHotspotsPanel hotspots={data.fileHotspots} />
                    </div>
                  </section>
                </>
              ) : (
                <>
                  <section className="mb-8">
                    <ConnectRepo repoCount={repos.length} hasRunner={runnerOk} syncError={syncError} />
                  </section>
                  <section>
                    <h2 className="text-xl font-medium">
                      Recent activity
                    </h2>
                    <div className="mt-6 rounded-lg border border-dashed border-border p-12 text-center">
                      <p className="text-muted-foreground">
                        No tasks yet. Go to{" "}
                        <Link
                          href="/chat"
                          className="font-medium text-primary hover:underline"
                        >
                          Chat
                        </Link>{" "}
                        to create your first task, or label a GitHub issue with{" "}
                        <code className="rounded bg-muted px-2 py-1 font-mono text-sm">
                          ai-agent
                        </code>
                        .
                      </p>
                    </div>
                  </section>
                </>
              ),
              prs: (
                <section>
                  <div className="rounded-lg border border-border bg-card p-6">
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
      </main>
    </div>
  );
}
