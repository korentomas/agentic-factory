import { NextResponse } from "next/server";
import { eq } from "drizzle-orm";
import { db } from "@/lib/db";
import { repositories } from "@/lib/db/schema";
import { createTaskThread, saveTaskMessage } from "@/lib/db/queries";
import type { RiskTier } from "@/lib/db/schema";

/**
 * POST /api/tasks/from-issue
 *
 * Called by GitHub Actions triage workflow to register an issue-triggered
 * task in the web DB so it appears in the /chat UI.
 *
 * Auth: X-Callback-Secret header (shared secret with CI).
 */
export async function POST(req: Request) {
  const secret = process.env.CALLBACK_SECRET;
  const provided = req.headers.get("x-callback-secret") ?? "";
  if (!secret || provided !== secret) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const body = await req.json();
  const {
    repoFullName,
    issueNumber,
    title,
    description,
    branch,
    baseBranch,
    riskTier,
    issueUrl,
  } = body;

  if (!repoFullName || !issueNumber || !title || !description) {
    return NextResponse.json(
      {
        error:
          "Missing required fields: repoFullName, issueNumber, title, description",
      },
      { status: 400 },
    );
  }

  // Find the user who owns this repository
  const [repo] = await db
    .select({ userId: repositories.userId })
    .from(repositories)
    .where(eq(repositories.fullName, repoFullName))
    .limit(1);

  if (!repo) {
    return NextResponse.json(
      { error: `No user found with repo ${repoFullName}` },
      { status: 404 },
    );
  }

  const repoUrl = `https://github.com/${repoFullName}`;
  const taskBranch = branch || `agent/cu-gh-${issueNumber}`;

  const thread = await createTaskThread({
    userId: repo.userId,
    repoUrl,
    branch: taskBranch,
    baseBranch: baseBranch || "main",
    title: `#${issueNumber}: ${title}`,
    description,
    riskTier: (riskTier as RiskTier) || "medium",
  });

  // Save the initial message with issue link
  await saveTaskMessage({
    threadId: thread.id,
    role: "system",
    content: issueUrl
      ? `Task created from GitHub issue [#${issueNumber}](${issueUrl}). Triage dispatched to agent pipeline.`
      : `Task created from GitHub issue #${issueNumber}. Triage dispatched to agent pipeline.`,
  });

  return NextResponse.json({ threadId: thread.id }, { status: 201 });
}
