import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { getTaskThreads, getRepositories } from "@/lib/db/queries";
import { TasksPageClient } from "./tasks-client";

export const metadata: Metadata = { title: "Tasks — LailaTov" };
export const dynamic = "force-dynamic";

export default async function TasksPage() {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const [threads, repos] = await Promise.all([
    getTaskThreads(session.user.id),
    getRepositories(session.user.id),
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
