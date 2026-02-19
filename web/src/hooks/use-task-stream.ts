"use client";

import { useState, useEffect, useRef, useCallback } from "react";

interface StreamMessage {
  id: string;
  role: string;
  content: string | null;
  toolName?: string | null;
  toolInput?: string | null;
  toolOutput?: string | null;
  createdAt: string;
}

interface ThreadStatus {
  id?: string;
  title?: string;
  status: string;
  engine?: string | null;
  model?: string | null;
  costUsd?: string | null;
  durationMs?: number | null;
  numTurns?: number | null;
  commitSha?: string | null;
  errorMessage?: string | null;
}

interface UseTaskStreamReturn {
  messages: StreamMessage[];
  threadStatus: ThreadStatus | null;
  isConnected: boolean;
  isComplete: boolean;
}

export function useTaskStream(threadId: string): UseTaskStreamReturn {
  const [messages, setMessages] = useState<StreamMessage[]>([]);
  const [threadStatus, setThreadStatus] = useState<ThreadStatus | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    if (!threadId) return;

    const es = new EventSource(`/api/tasks/${threadId}/stream`);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
    };

    es.onmessage = (event) => {
      try {
        const parsed = JSON.parse(event.data) as {
          type: string;
          data: Record<string, unknown>;
          timestamp: string;
        };

        switch (parsed.type) {
          case "init": {
            const initData = parsed.data;
            const initMessages = (initData.messages ?? []) as StreamMessage[];
            setMessages(initMessages);

            const thread = initData.thread as Record<string, unknown> | undefined;
            setThreadStatus({
              id: (thread?.id as string) ?? threadId,
              title: thread?.title as string | undefined,
              status: (initData.status as string) ?? "pending",
              engine: thread?.engine as string | null | undefined,
              model: thread?.model as string | null | undefined,
            });
            break;
          }

          case "message": {
            const msg = parsed.data as unknown as StreamMessage;
            setMessages((prev) => [...prev, msg]);
            break;
          }

          case "status": {
            const statusData = parsed.data;
            setThreadStatus((prev) => ({
              ...prev,
              status: (statusData.status as string) ?? prev?.status ?? "pending",
            }));
            break;
          }

          case "complete": {
            const completeData = parsed.data;
            setThreadStatus((prev) => ({
              ...prev,
              status: (completeData.status as string) ?? prev?.status ?? "complete",
              commitSha: (completeData.commitSha as string | null) ?? prev?.commitSha,
              costUsd: (completeData.costUsd as string | null) ?? prev?.costUsd,
              durationMs: (completeData.durationMs as number | null) ?? prev?.durationMs,
              errorMessage: (completeData.errorMessage as string | null) ?? prev?.errorMessage,
            }));
            setIsComplete(true);
            es.close();
            break;
          }
        }
      } catch {
        // Ignore malformed events
      }
    };

    es.onerror = () => {
      setIsConnected(false);
      // EventSource auto-reconnects on error
    };

    return () => {
      es.close();
      eventSourceRef.current = null;
    };
  }, [threadId]);

  return { messages, threadStatus, isConnected, isComplete };
}
