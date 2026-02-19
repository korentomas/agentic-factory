import type { Metadata } from "next";
import { redirect, notFound } from "next/navigation";
import { auth } from "@/lib/auth";
import { getTaskThread, getTaskPlans } from "@/lib/db/queries";
import { ThreadView } from "./thread-view";

export const metadata: Metadata = { title: "Task Execution — LailaTov" };
export const dynamic = "force-dynamic";

export default async function TaskThreadPage({
  params,
}: {
  params: Promise<{ threadId: string }>;
}) {
  const session = await auth();
  if (!session?.user?.id) redirect("/login");

  const { threadId } = await params;
  const thread = await getTaskThread(threadId);
  if (!thread || thread.userId !== session.user.id) notFound();

  const plans = await getTaskPlans(threadId);

  return (
    <ThreadView
      threadId={thread.id}
      initialThread={{
        title: thread.title,
        status: thread.status,
        engine: thread.engine,
        model: thread.model,
        repoUrl: thread.repoUrl,
        branch: thread.branch,
        costUsd: thread.costUsd ? Number(thread.costUsd) : 0,
        durationMs: thread.durationMs ?? 0,
      }}
      initialPlans={plans.map((p) => ({
        revision: p.revision,
        steps:
          (p.steps as Array<{
            title: string;
            description: string;
            status: "pending" | "in_progress" | "completed" | "skipped";
          }>) ?? [],
        createdBy: p.createdBy ?? "agent",
        createdAt: p.createdAt,
      }))}
    />
  );
}
