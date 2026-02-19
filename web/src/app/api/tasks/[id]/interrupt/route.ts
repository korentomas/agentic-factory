import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { getTaskThread, saveTaskMessage } from "@/lib/db/queries";

export async function POST(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { id } = await params;
  const thread = await getTaskThread(id);

  if (!thread || thread.userId !== session.user.id) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  if (thread.status !== "running") {
    return NextResponse.json(
      { error: "Thread is not running" },
      { status: 400 },
    );
  }

  const body = await req.json();
  const { content } = body;

  if (!content || typeof content !== "string" || content.trim().length === 0) {
    return NextResponse.json(
      { error: "Content is required" },
      { status: 400 },
    );
  }

  const message = await saveTaskMessage({
    threadId: id,
    role: "manager",
    content: content.trim(),
  });

  // If content is "cancel", forward to Runner
  if (content.trim().toLowerCase() === "cancel") {
    const runnerUrl = process.env.RUNNER_API_URL;
    if (runnerUrl) {
      try {
        await fetch(`${runnerUrl}/tasks/${id}/cancel`, {
          method: "POST",
          headers: {
            Authorization: `Bearer ${process.env.RUNNER_API_KEY || ""}`,
          },
        });
      } catch {
        // Runner cancel is best-effort
      }
    }
  }

  return NextResponse.json({ messageId: message.id }, { status: 201 });
}
