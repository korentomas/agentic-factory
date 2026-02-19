import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { createTaskThread, saveTaskMessage, updateTaskThread } from "@/lib/db/queries";
import type { RiskTier } from "@/lib/db/schema";

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const { repoUrl, branch, baseBranch, title, description, engine, model, riskTier } = body;

  if (!repoUrl || !branch || !title || !description) {
    return NextResponse.json(
      { error: "Missing required fields: repoUrl, branch, title, description" },
      { status: 400 },
    );
  }

  const thread = await createTaskThread({
    userId: session.user.id,
    repoUrl,
    branch,
    baseBranch,
    title,
    description,
    engine,
    model,
    riskTier: riskTier as RiskTier | undefined,
  });

  // Save the initial human message
  await saveTaskMessage({
    threadId: thread.id,
    role: "human",
    content: description,
  });

  // Dispatch to Agent Runner (non-blocking — thread is created regardless)
  const runnerUrl = process.env.RUNNER_API_URL;
  if (runnerUrl) {
    try {
      const webUrl = process.env.WEB_URL || "http://localhost:3000";
      const resp = await fetch(`${runnerUrl}/tasks`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${process.env.RUNNER_API_KEY || ""}`,
        },
        body: JSON.stringify({
          task_id: thread.id,
          repo_url: repoUrl,
          branch,
          base_branch: baseBranch || "main",
          title,
          description,
          engine: engine || null,
          model: model || null,
          risk_tier: riskTier || "medium",
          github_token: process.env.GITHUB_TOKEN || null,
          callback_url: `${webUrl}/api/tasks/${thread.id}/webhook`,
        }),
      });

      if (resp.ok) {
        await updateTaskThread(thread.id, { status: "running" });
      }
    } catch {
      // Runner unavailable — thread stays pending, user can retry
    }
  }

  return NextResponse.json({ threadId: thread.id }, { status: 201 });
}
