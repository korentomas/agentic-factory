import { NextResponse } from "next/server";
import { getTaskThread, updateTaskThread, saveTaskMessage, saveTaskPlan } from "@/lib/db/queries";
import type { TaskThreadStatus, TaskMessageRole, TaskPlanStepStatus } from "@/lib/db/schema";

/** Validate Runner API key from Authorization header. */
function validateAuth(req: Request): boolean {
  const apiKey = process.env.RUNNER_API_KEY;
  if (!apiKey) return false;
  const auth = req.headers.get("authorization") ?? "";
  return auth === `Bearer ${apiKey}`;
}

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  if (!validateAuth(req)) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const thread = await getTaskThread(id);
  if (!thread) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  const body = await req.json();
  const { type } = body;

  switch (type) {
    case "status": {
      const status = body.status as TaskThreadStatus;
      await updateTaskThread(id, { status });
      break;
    }

    case "message": {
      await saveTaskMessage({
        threadId: id,
        role: (body.role as TaskMessageRole) ?? "system",
        content: body.content ?? null,
      });
      break;
    }

    case "complete": {
      await updateTaskThread(id, {
        status: (body.status as TaskThreadStatus) ?? "complete",
        commitSha: body.commitSha ?? undefined,
        costUsd: body.costUsd != null ? String(body.costUsd) : undefined,
        durationMs: body.durationMs ?? undefined,
        engine: body.engine ?? undefined,
        model: body.model ?? undefined,
      });
      await saveTaskMessage({
        threadId: id,
        role: "system",
        content: body.commitSha
          ? `Task complete. Commit: ${body.commitSha}`
          : "Task complete. No changes committed.",
      });
      break;
    }

    case "failed": {
      await updateTaskThread(id, {
        status: "failed",
        errorMessage: body.errorMessage ?? "Unknown error",
      });
      await saveTaskMessage({
        threadId: id,
        role: "system",
        content: `Task failed: ${body.errorMessage ?? "Unknown error"}`,
      });
      break;
    }

    case "cancelled": {
      await updateTaskThread(id, { status: "cancelled" });
      await saveTaskMessage({
        threadId: id,
        role: "system",
        content: "Task was cancelled.",
      });
      break;
    }

    case "plan": {
      const steps = (body.steps ?? []) as Array<{
        title: string;
        description: string;
        status: TaskPlanStepStatus;
      }>;
      await saveTaskPlan({
        threadId: id,
        revision: body.revision ?? 1,
        steps,
        createdBy: body.createdBy ?? "agent",
      });
      break;
    }

    default:
      return NextResponse.json({ error: `Unknown event type: ${type}` }, { status: 400 });
  }

  return NextResponse.json({ ok: true });
}
