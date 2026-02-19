/** Thread summary for list views. */
export interface TaskThreadSummary {
  id: string;
  title: string;
  repoUrl: string;
  branch: string;
  status: string;
  engine: string | null;
  model: string | null;
  costUsd: number;
  durationMs: number;
  createdAt: Date;
  updatedAt: Date;
}

/** SSE event types from the task stream. */
export type TaskStreamEventType =
  | "status"
  | "message"
  | "plan"
  | "progress"
  | "cost"
  | "complete"
  | "error";

/** SSE event payload. */
export interface TaskStreamEvent {
  type: TaskStreamEventType;
  data: Record<string, unknown>;
  timestamp: string;
}

/** Plan step for progress visualization. */
export interface PlanStep {
  title: string;
  description: string;
  status: "pending" | "in_progress" | "completed" | "skipped";
}

/** Task creation request. */
export interface CreateTaskRequest {
  repoUrl: string;
  branch: string;
  baseBranch?: string;
  title: string;
  description: string;
  engine?: string;
  model?: string;
  riskTier?: string;
}
