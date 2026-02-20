"use client";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  HoverCard,
  HoverCardContent,
  HoverCardTrigger,
} from "@/components/ui/hover-card";
import { Clock, Coins, Zap } from "lucide-react";

interface TokenUsageProps {
  costUsd?: string | null;
  durationMs?: number | null;
  engine?: string | null;
  model?: string | null;
  numTurns?: number | null;
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  const remaining = seconds % 60;
  return `${minutes}m ${remaining}s`;
}

export function TokenUsage({
  costUsd,
  durationMs,
  engine,
  model,
  numTurns,
}: TokenUsageProps) {
  const hasCost = costUsd != null && costUsd !== "0";
  const hasDuration = durationMs != null && durationMs > 0;

  if (!hasCost && !hasDuration) return null;

  return (
    <HoverCard>
      <HoverCardTrigger asChild>
        <button className="hover:bg-muted/50 flex items-center gap-2 rounded-md p-2 transition-colors">
          {hasCost && (
            <Badge variant="secondary" className="text-xs">
              ${parseFloat(costUsd!).toFixed(2)}
            </Badge>
          )}
          {hasDuration && (
            <Badge variant="outline" className="text-xs">
              <Clock className="mr-1 h-3 w-3" />
              {formatDuration(durationMs!)}
            </Badge>
          )}
        </button>
      </HoverCardTrigger>
      <HoverCardContent className="w-64">
        <div className="space-y-3">
          <h4 className="text-sm font-semibold">Execution Details</h4>

          {hasCost && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Coins className="h-3 w-3 text-amber-500" />
                <span className="text-muted-foreground text-xs font-medium">
                  Cost
                </span>
              </div>
              <span className="text-sm font-semibold">
                ${parseFloat(costUsd!).toFixed(4)}
              </span>
            </div>
          )}

          {hasDuration && (
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5">
                <Clock className="h-3 w-3 text-blue-500" />
                <span className="text-muted-foreground text-xs font-medium">
                  Duration
                </span>
              </div>
              <span className="text-sm font-semibold">
                {formatDuration(durationMs!)}
              </span>
            </div>
          )}

          {numTurns != null && numTurns > 0 && (
            <>
              <Separator />
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5">
                  <Zap className="h-3 w-3 text-purple-500" />
                  <span className="text-muted-foreground text-xs font-medium">
                    Turns
                  </span>
                </div>
                <span className="text-sm font-semibold">{numTurns}</span>
              </div>
            </>
          )}

          {(engine || model) && (
            <>
              <Separator />
              <div className="space-y-1.5">
                {engine && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-xs">
                      Engine
                    </span>
                    <Badge variant="outline" className="text-xs">
                      {engine}
                    </Badge>
                  </div>
                )}
                {model && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground text-xs">Model</span>
                    <Badge variant="outline" className="text-xs">
                      {model}
                    </Badge>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      </HoverCardContent>
    </HoverCard>
  );
}
