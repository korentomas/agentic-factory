import { createAnthropic } from "@ai-sdk/anthropic";
import { streamText, UIMessage } from "ai";
import { auth } from "@/lib/auth";
import { detectIntent, stripPrefix } from "@/lib/chat/intent";
import { getOrCreateChatSession, saveChatMessage } from "@/lib/db/queries";
import { NextResponse } from "next/server";

export const maxDuration = 60;

function getModel() {
  const openrouterKey = process.env.OPENROUTER_API_KEY;
  if (openrouterKey) {
    const provider = createAnthropic({
      baseURL: "https://openrouter.ai/api/v1",
      apiKey: openrouterKey,
    });
    return provider("anthropic/claude-sonnet-4");
  }
  const provider = createAnthropic();
  return provider("claude-sonnet-4-20250514");
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { messages }: { messages: UIMessage[] } = await req.json();
  const lastMessage = messages[messages.length - 1];
  const userText = lastMessage?.parts
    ?.filter((p: { type: string }) => p.type === "text")
    .map((p: { type: string; text?: string }) => p.text ?? "")
    .join("") ?? "";

  const intent = detectIntent(userText);
  const chatSession = await getOrCreateChatSession(session.user.id);

  // Save user message
  await saveChatMessage({
    sessionId: chatSession.id,
    role: "user",
    content: userText,
    metadata: { intent },
  });

  if (intent === "task") {
    const taskDescription = stripPrefix(userText);
    const response = `I'll create a task for: "${taskDescription}"\n\nThis will be dispatched to the LailaTov runner when a repository is connected. For now, you can create a GitHub issue with the \`ai-agent\` label to trigger the pipeline.`;

    await saveChatMessage({
      sessionId: chatSession.id,
      role: "assistant",
      content: response,
      metadata: { intent: "task", taskDescription },
    });

    return NextResponse.json({
      role: "assistant",
      content: response,
    });
  }

  // Quick path: Claude API (supports both Anthropic direct and OpenRouter)
  const result = streamText({
    model: getModel(),
    system: "You are LailaTov, an AI coding assistant. You help developers understand their codebase, review code, and answer technical questions. Be concise and helpful. Use code blocks with language tags when showing code.",
    messages: messages.map((m) => ({
      role: m.role as "user" | "assistant",
      content: m.parts
        ?.filter((p: { type: string }) => p.type === "text")
        .map((p: { type: string; text?: string }) => p.text ?? "")
        .join("") ?? "",
    })),
  });

  // Save assistant response after stream completes
  void Promise.resolve(result.text).then(async (text) => {
    await saveChatMessage({
      sessionId: chatSession.id,
      role: "assistant",
      content: text,
    });
  }).catch(() => {});

  return result.toUIMessageStreamResponse();
}
