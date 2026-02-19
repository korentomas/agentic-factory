import { auth } from "@/lib/auth";
import { getTaskThread, getTaskMessages, getTaskPlans } from "@/lib/db/queries";
import type { TaskThreadStatus } from "@/lib/db/schema";

export const dynamic = "force-dynamic";

const TERMINAL_STATUSES: TaskThreadStatus[] = ["complete", "failed", "cancelled"];
const POLL_INTERVAL_MS = 2000;

export async function GET(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const session = await auth();
  if (!session?.user?.id) {
    return new Response(JSON.stringify({ error: "Unauthorized" }), {
      status: 401,
      headers: { "Content-Type": "application/json" },
    });
  }

  const { id } = await params;
  const thread = await getTaskThread(id);

  if (!thread || thread.userId !== session.user.id) {
    return new Response(JSON.stringify({ error: "Not found" }), {
      status: 404,
      headers: { "Content-Type": "application/json" },
    });
  }

  let cancelled = false;
  req.signal.addEventListener("abort", () => {
    cancelled = true;
  });

  const stream = new ReadableStream({
    async start(controller) {
      const encoder = new TextEncoder();

      const send = (event: string, data: Record<string, unknown>) => {
        const payload = JSON.stringify({ type: event, data, timestamp: new Date().toISOString() });
        controller.enqueue(encoder.encode(`data: ${payload}\n\n`));
      };

      // Send initial state
      const messages = await getTaskMessages(id);
      send("init", {
        status: thread.status,
        thread: {
          id: thread.id,
          title: thread.title,
          repoUrl: thread.repoUrl,
          branch: thread.branch,
          status: thread.status,
          engine: thread.engine,
          model: thread.model,
        },
        messages: messages.map((m) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          toolName: m.toolName,
          toolInput: m.toolInput,
          toolOutput: m.toolOutput,
          metadata: m.metadata,
          createdAt: m.createdAt.toISOString(),
        })),
      });

      // If already terminal, send complete and close
      if (TERMINAL_STATUSES.includes(thread.status as TaskThreadStatus)) {
        send("complete", { status: thread.status });
        controller.close();
        return;
      }

      // Poll for new messages, status changes, and plan updates
      let lastMessageCount = messages.length;
      let lastStatus = thread.status;
      let lastPlanCount = 0;

      const poll = async () => {
        while (!cancelled) {
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          if (cancelled) break;

          try {
            const currentThread = await getTaskThread(id);
            if (!currentThread) break;

            // Check for new messages
            const currentMessages = await getTaskMessages(id);
            if (currentMessages.length > lastMessageCount) {
              const newMessages = currentMessages.slice(lastMessageCount);
              for (const m of newMessages) {
                send("message", {
                  id: m.id,
                  role: m.role,
                  content: m.content,
                  toolName: m.toolName,
                  toolInput: m.toolInput,
                  toolOutput: m.toolOutput,
                  metadata: m.metadata,
                  createdAt: m.createdAt.toISOString(),
                });
              }
              lastMessageCount = currentMessages.length;
            }

            // Check for new/updated plans
            const plans = await getTaskPlans(id);
            if (plans.length > lastPlanCount) {
              const latestPlan = plans[plans.length - 1];
              send("plan", {
                revision: latestPlan.revision,
                steps: latestPlan.steps,
                createdBy: latestPlan.createdBy,
              });
              lastPlanCount = plans.length;
            }

            // Check for status change
            if (currentThread.status !== lastStatus) {
              send("status", { status: currentThread.status });
              lastStatus = currentThread.status;
            }

            // Check if terminal
            if (TERMINAL_STATUSES.includes(currentThread.status as TaskThreadStatus)) {
              send("complete", {
                status: currentThread.status,
                commitSha: currentThread.commitSha,
                costUsd: currentThread.costUsd,
                durationMs: currentThread.durationMs,
                errorMessage: currentThread.errorMessage,
              });
              break;
            }
          } catch {
            // If DB query fails, break to avoid infinite loop
            break;
          }
        }

        controller.close();
      };

      poll();
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    },
  });
}
