import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { createTaskThread, saveTaskMessage } from "@/lib/db/queries";
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

  return NextResponse.json({ threadId: thread.id }, { status: 201 });
}
