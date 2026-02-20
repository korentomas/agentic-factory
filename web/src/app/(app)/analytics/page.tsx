"use client";

import Link from "next/link";
import useSWR from "swr";
import { Skeleton } from "@/components/ui/skeleton";
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
import type { DashboardData } from "@/lib/data";

type AnalyticsResponse = DashboardData & {
  repoCount: number;
  runnerOk: boolean;
  userName: string | null;
};

const fetcher = (url: string) => fetch(url).then((r) => r.json());

export default function AnalyticsPage() {
  const { data, isLoading } = useSWR<AnalyticsResponse>(
    "/api/analytics",
    fetcher,
    { refreshInterval: 30_000 },
  );

  const hasData = (data?.outcomes?.length ?? 0) > 0;
  const firstName = data?.userName?.split(" ")[0] || "developer";

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <AppHeader showBrand />

      <main className="mx-auto w-full max-w-7xl px-6 py-8">
        {/* Header */}
        <div className="mb-8">
          {isLoading && !data ? (
            <>
              <Skeleton className="h-9 w-80" />
              <Skeleton className="mt-2 h-5 w-64" />
            </>
          ) : (
            <>
              <h1 className="text-3xl font-semibold tracking-tight">
                Welcome back, {firstName}
              </h1>
              <p className="mt-2 text-muted-foreground">
                Your autonomous code factory is{" "}
                {hasData ? "running" : "ready to start"}.
              </p>
            </>
          )}
        </div>

        {/* Stats overview */}
        <section className="mb-8">
          {isLoading && !data ? (
            <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
              <Skeleton className="h-24 rounded-lg" />
              <Skeleton className="h-24 rounded-lg" />
              <Skeleton className="h-24 rounded-lg" />
              <Skeleton className="h-24 rounded-lg" />
            </div>
          ) : data ? (
            <StatsCards stats={data.stats} />
          ) : null}
        </section>

        {isLoading && !data ? (
          <div className="space-y-6">
            <Skeleton className="h-10 w-96 rounded-lg" />
            <Skeleton className="h-64 rounded-lg" />
          </div>
        ) : data ? (
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
                    <h2 className="mb-4 text-xl font-medium">Code Quality</h2>
                    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                      <CodeRetentionPanel retention={data.codeRetention} />
                      <FileHotspotsPanel hotspots={data.fileHotspots} />
                    </div>
                  </section>
                </>
              ) : (
                <>
                  <section className="mb-8">
                    <ConnectRepo
                      repoCount={data.repoCount}
                      hasRunner={data.runnerOk}
                    />
                  </section>
                  <section>
                    <h2 className="text-xl font-medium">Recent activity</h2>
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
        ) : null}
      </main>
    </div>
  );
}
