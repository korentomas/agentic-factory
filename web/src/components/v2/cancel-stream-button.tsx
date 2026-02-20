"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Loader2, Square } from "lucide-react";

interface CancelStreamButtonProps {
  threadId: string;
  isRunning: boolean;
}

export function CancelStreamButton({
  threadId,
  isRunning,
}: CancelStreamButtonProps) {
  const [cancelling, setCancelling] = useState(false);

  if (!isRunning) return null;

  const handleCancel = async () => {
    setCancelling(true);
    try {
      await fetch(`/api/tasks/${threadId}/interrupt`, { method: "POST" });
    } catch {
      // Interrupt request failed silently — SSE will reflect final state
    } finally {
      setCancelling(false);
    }
  };

  return (
    <Button
      onClick={handleCancel}
      size="sm"
      variant="destructive"
      className="h-8 px-3 text-xs"
      disabled={cancelling}
    >
      {cancelling ? (
        <>
          <Square className="mr-1 h-3 w-3 animate-pulse" />
          <span className="animate-pulse">Stopping...</span>
        </>
      ) : (
        <>
          <Loader2 className="mr-1 h-3 w-3 animate-spin" />
          Stop Execution
        </>
      )}
    </Button>
  );
}
