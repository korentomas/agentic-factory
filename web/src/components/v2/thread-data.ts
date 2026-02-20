import type { ThreadMetadata, ThreadStatus } from "./types";

export interface TaskThreadRow {
  id: string;
  repoUrl: string;
  branch: string;
  baseBranch: string;
  title: string;
  description: string;
  status: ThreadStatus;
  engine: string | null;
  model: string | null;
  costUsd: string | null;
  durationMs: number | null;
  createdAt: string;
  updatedAt: string;
}

export function toThreadMetadata(row: TaskThreadRow): ThreadMetadata {
  return {
    id: row.id,
    title: row.title,
    repository: row.repoUrl,
    branch: row.branch,
    baseBranch: row.baseBranch,
    status: row.status,
    engine: row.engine,
    model: row.model,
    costUsd: row.costUsd ? Number(row.costUsd) : 0,
    durationMs: row.durationMs ?? 0,
    lastActivity: new Date(row.updatedAt),
    createdAt: new Date(row.createdAt),
  };
}

export const fetcher = (url: string) => fetch(url).then((r) => r.json());
