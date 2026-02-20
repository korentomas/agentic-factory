import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { after } from "next/server";
import { auth } from "@/lib/auth";
import { getTaskThreads, getRepositories } from "@/lib/db/queries";
import { syncGitHubReposDebounced } from "@/lib/github/sync-repos";
import { TasksPageClient } from "./tasks-client";

export const metadata: Metadata = { title: "Tasks — LailaTov" };
export const dynamic = "force-dynamic";

export default async function TasksPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const userId = session.user.id;
  const accessToken = session.accessToken;

  // Fire-and-forget: sync runs AFTER HTML is sent to the client
  after(async () => {
    try {
      await syncGitHubReposDebounced(userId, accessToken);
    } catch (err) {
      console.error("[tasks] syncGitHubRepos threw:", err);
    }
  });

  const [threads, repos] = await Promise.all([
    getTaskThreads(userId),
    getRepositories(userId),
  ]);

  const repoOptions = repos.map((r) => ({
    fullName: r.fullName,
    url: `https://github.com/${r.fullName}`,
  }));

  return (
    <TasksPageClient
      threads={threads.map((t) => ({
        id: t.id,
        title: t.title,
        repoUrl: t.repoUrl,
        branch: t.branch,
        status: t.status,
        engine: t.engine,
        model: t.model,
        costUsd: t.costUsd ? Number(t.costUsd) : 0,
        durationMs: t.durationMs ?? 0,
        createdAt: t.createdAt,
        updatedAt: t.updatedAt,
      }))}
      repos={repoOptions}
    />
  );
}
