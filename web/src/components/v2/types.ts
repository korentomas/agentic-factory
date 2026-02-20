export interface ThreadMetadata {
  id: string;
  title: string;
  repository: string;
  branch: string;
  baseBranch?: string;
  status: ThreadStatus;
  engine?: string | null;
  model?: string | null;
  costUsd: number;
  durationMs: number;
  lastActivity: Date;
  createdAt: Date;
}

export type ThreadStatus =
  | "pending"
  | "running"
  | "committing"
  | "complete"
  | "failed"
  | "cancelled";

export interface TaskPlan {
  id: string;
  threadId: string;
  revision: number;
  steps: TaskStep[];
  createdBy: string;
  createdAt: Date;
}

export interface TaskStep {
  title: string;
  description?: string;
  status: "pending" | "in_progress" | "complete" | "failed" | "skipped";
}

export interface TaskMessage {
  id: string;
  threadId: string;
  role: "human" | "assistant" | "tool" | "system" | "manager";
  content: string;
  toolName?: string | null;
  toolInput?: string | null;
  toolOutput?: string | null;
  metadata?: Record<string, unknown> | null;
  createdAt: Date;
}

export interface RepoOption {
  fullName: string;
  url: string;
  installationId?: number;
}
