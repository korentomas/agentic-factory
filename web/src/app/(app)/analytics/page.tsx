import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { after } from "next/server";
import Link from "next/link";
import { Suspense } from "react";
import { auth } from "@/lib/auth";
import { loadDashboardData } from "@/lib/data";
import { getRepositories } from "@/lib/db/queries";
import { syncGitHubReposDebounced } from "@/lib/github/sync-repos";
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
import { AppHeader } from "@/components/v2/app-header";

export const metadata: Metadata = {
  title: "Analytics — LailaTov",
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

export default async function AnalyticsPage() {
  const session = await auth();

  if (!session?.user) {
    redirect("/login");
  }

  const user = session.user;
  const accessToken = session.accessToken;

  const userId = session.user.id;

  // Fire-and-forget: sync runs AFTER HTML is sent to the client
  if (userId) {
    after(async () => {
      try {
        await syncGitHubReposDebounced(userId, accessToken);
      } catch (err) {
        console.error("[analytics] syncGitHubRepos threw:", err);
      }
    });
  }

  // Load dashboard data and check setup status in parallel
  const [data, repos, runnerOk] = await Promise.all([
    loadDashboardData(accessToken),
    userId ? getRepositories(userId) : Promise.resolve([]),
    checkRunnerHealth(),
  ]);
  const hasData = data.outcomes.length > 0;

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <AppHeader showBrand />

      <main className="mx-auto w-full max-w-7xl px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-3xl font-semibold tracking-tight">
            Welcome back, {user.name?.split(" ")[0] || "developer"}
          </h1>
          <p className="mt-2 text-muted-foreground">
            Your autonomous code factory is{" "}
            {hasData ? "running" : "ready to start"}.
          </p>
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
                    <ConnectRepo repoCount={repos.length} hasRunner={runnerOk} />
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
