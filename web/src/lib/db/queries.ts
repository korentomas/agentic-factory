import { and, asc, count, desc, eq, sql } from "drizzle-orm";
import { db } from "@/lib/db";
import {
  agentOutcomes,
  chatMessages,
  chatSessions,
  repositories,
  subscriptions,
  type OutcomeValue,
  type CheckStatus,
  type RiskTier,
  type SubscriptionStatus,
} from "@/lib/db/schema";
import type {
  CheckHealth,
  DashboardStats,
  EngineBreakdown,
  FileHotspot,
  ModelBreakdown,
  RiskBreakdown,
} from "@/lib/data/types";

/* ─────────────────────────────────────────────────────────
 * Dashboard stats
 * ───────────────────────────────────────────────────────── */

/** Get high-level dashboard stats for a user. */
export async function getDashboardStats(
  userId: string,
): Promise<DashboardStats> {
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

  const allOutcomes = await db
    .select({
      outcome: agentOutcomes.outcome,
      costUsd: agentOutcomes.costUsd,
      durationMs: agentOutcomes.durationMs,
      timestamp: agentOutcomes.timestamp,
    })
    .from(agentOutcomes)
    .where(eq(agentOutcomes.userId, userId));

  const total = allOutcomes.length;
  const thisMonth = allOutcomes.filter((o) => o.timestamp >= monthStart);
  const clean = allOutcomes.filter((o) => o.outcome === "clean");

  const totalCost = allOutcomes.reduce(
    (sum, o) => sum + (o.costUsd ? Number(o.costUsd) : 0),
    0,
  );
  const monthCost = thisMonth.reduce(
    (sum, o) => sum + (o.costUsd ? Number(o.costUsd) : 0),
    0,
  );

  const durations = allOutcomes
    .filter((o) => o.durationMs !== null)
    .map((o) => o.durationMs!);
  const avgDuration =
    durations.length > 0
      ? durations.reduce((a, b) => a + b, 0) / durations.length
      : 0;

  return {
    totalTasks: total,
    tasksThisMonth: thisMonth.length,
    prsShipped: clean.length,
    prsClean: clean.length,
    prsFailed: total - clean.length,
    successRate: total > 0 ? clean.length / total : 0,
    totalCost,
    costThisMonth: monthCost,
    avgDurationMs: avgDuration,
  };
}

/* ─────────────────────────────────────────────────────────
 * Outcomes list
 * ───────────────────────────────────────────────────────── */

/** Inferred outcome row type from the agentOutcomes table. */
export type OutcomeRow = typeof agentOutcomes.$inferSelect;

/** Fetch outcomes for a user, sorted by timestamp descending. */
export async function getOutcomes(
  userId: string,
  limit: number = 50,
): Promise<OutcomeRow[]> {
  return db
    .select()
    .from(agentOutcomes)
    .where(eq(agentOutcomes.userId, userId))
    .orderBy(desc(agentOutcomes.timestamp))
    .limit(limit);
}

/* ─────────────────────────────────────────────────────────
 * Engine breakdown
 * ───────────────────────────────────────────────────────── */

/** Group outcomes by engine with success rates, avg cost, and avg duration. */
export async function getEngineBreakdown(
  userId: string,
): Promise<EngineBreakdown[]> {
  const rows = await db
    .select({
      engine: agentOutcomes.engine,
      count: count(),
      successCount: count(
        sql`CASE WHEN ${agentOutcomes.outcome} = 'clean' THEN 1 END`,
      ),
      totalCost: sql<string>`COALESCE(SUM(${agentOutcomes.costUsd}), 0)`,
      totalDuration: sql<number>`COALESCE(SUM(${agentOutcomes.durationMs}), 0)`,
      durationCount: count(agentOutcomes.durationMs),
    })
    .from(agentOutcomes)
    .where(eq(agentOutcomes.userId, userId))
    .groupBy(agentOutcomes.engine);

  return rows.map((r) => {
    const engine = r.engine ?? "claude-code";
    const total = r.count;
    const successCount = r.successCount;
    return {
      engine,
      count: total,
      successCount,
      failureCount: total - successCount,
      successRate: total > 0 ? successCount / total : 0,
      avgCost: total > 0 ? Number(r.totalCost) / total : 0,
      avgDuration: r.durationCount > 0 ? r.totalDuration / r.durationCount : 0,
    };
  });
}

/* ─────────────────────────────────────────────────────────
 * Model breakdown
 * ───────────────────────────────────────────────────────── */

/** Group outcomes by model with success rates and stage info. */
export async function getModelBreakdown(
  userId: string,
): Promise<ModelBreakdown[]> {
  const rows = await db
    .select({
      model: agentOutcomes.model,
      reviewModel: agentOutcomes.reviewModel,
      outcome: agentOutcomes.outcome,
    })
    .from(agentOutcomes)
    .where(eq(agentOutcomes.userId, userId));

  const groups = new Map<
    string,
    { outcomes: typeof rows; hasReviewModel: boolean }
  >();

  for (const row of rows) {
    const model = row.model ?? "unknown";
    const existing = groups.get(model) ?? { outcomes: [], hasReviewModel: false };
    existing.outcomes.push(row);
    if (row.reviewModel) {
      existing.hasReviewModel = true;
    }
    groups.set(model, existing);
  }

  return Array.from(groups.entries()).map(([model, data]) => {
    const total = data.outcomes.length;
    const successCount = data.outcomes.filter(
      (o) => o.outcome === "clean",
    ).length;
    const stages = data.hasReviewModel ? ["write", "review"] : ["write"];

    return {
      model,
      count: total,
      successCount,
      failureCount: total - successCount,
      successRate: total > 0 ? successCount / total : 0,
      stages,
    };
  });
}

/* ─────────────────────────────────────────────────────────
 * Check health
 * ───────────────────────────────────────────────────────── */

/** Aggregate check pass/fail/skip rates across all user outcomes. */
export async function getCheckHealth(
  userId: string,
): Promise<CheckHealth[]> {
  const rows = await db
    .select({
      checksGate: agentOutcomes.checksGate,
      checksTests: agentOutcomes.checksTests,
      checksReview: agentOutcomes.checksReview,
      checksSpecAudit: agentOutcomes.checksSpecAudit,
    })
    .from(agentOutcomes)
    .where(eq(agentOutcomes.userId, userId));

  const checks: {
    name: string;
    key: "checksGate" | "checksTests" | "checksReview" | "checksSpecAudit";
    displayName: string;
  }[] = [
    { name: "gate", key: "checksGate", displayName: "Gate" },
    { name: "tests", key: "checksTests", displayName: "Tests" },
    { name: "review", key: "checksReview", displayName: "Review" },
    { name: "spec_audit", key: "checksSpecAudit", displayName: "Spec Audit" },
  ];

  return checks.map(({ key, displayName }) => {
    let passed = 0;
    let failed = 0;
    let skipped = 0;

    for (const row of rows) {
      const val = row[key];
      if (val === "success") passed++;
      else if (val === "failure") failed++;
      else skipped++;
    }

    const evaluated = passed + failed;
    return {
      name: displayName,
      passed,
      failed,
      skipped,
      passRate: evaluated > 0 ? passed / evaluated : 0,
    };
  });
}

/* ─────────────────────────────────────────────────────────
 * Risk breakdown
 * ───────────────────────────────────────────────────────── */

/** Group outcomes by risk tier with success rates. */
export async function getRiskBreakdown(
  userId: string,
): Promise<RiskBreakdown[]> {
  const rows = await db
    .select({
      riskTier: agentOutcomes.riskTier,
      count: count(),
      successCount: count(
        sql`CASE WHEN ${agentOutcomes.outcome} = 'clean' THEN 1 END`,
      ),
    })
    .from(agentOutcomes)
    .where(eq(agentOutcomes.userId, userId))
    .groupBy(agentOutcomes.riskTier);

  return rows
    .map((r) => ({
      tier: r.riskTier as RiskTier,
      count: r.count,
      successCount: r.successCount,
      failureCount: r.count - r.successCount,
      successRate: r.count > 0 ? r.successCount / r.count : 0,
    }))
    .filter((r) => r.count > 0);
}

/* ─────────────────────────────────────────────────────────
 * File hotspots
 * ───────────────────────────────────────────────────────── */

/** Find most-changed files across a user's outcomes. */
export async function getFileHotspots(
  userId: string,
): Promise<FileHotspot[]> {
  const rows = await db
    .select({
      filesChanged: agentOutcomes.filesChanged,
      outcome: agentOutcomes.outcome,
    })
    .from(agentOutcomes)
    .where(eq(agentOutcomes.userId, userId));

  const fileMap = new Map<
    string,
    { appearances: number; inSuccessful: number; inFailed: number }
  >();

  for (const row of rows) {
    const files = row.filesChanged ?? [];
    for (const filePath of files) {
      const entry = fileMap.get(filePath) ?? {
        appearances: 0,
        inSuccessful: 0,
        inFailed: 0,
      };
      entry.appearances++;
      if (row.outcome === "clean") entry.inSuccessful++;
      else entry.inFailed++;
      fileMap.set(filePath, entry);
    }
  }

  return Array.from(fileMap.entries())
    .map(([path, data]) => ({ path, ...data }))
    .sort((a, b) => b.appearances - a.appearances)
    .slice(0, 20);
}

/* ─────────────────────────────────────────────────────────
 * Subscription
 * ───────────────────────────────────────────────────────── */

/** Inferred subscription row type. */
export type SubscriptionRow = typeof subscriptions.$inferSelect;

/** Get the active subscription for a user (if any). */
export async function getUserSubscription(
  userId: string,
): Promise<SubscriptionRow | null> {
  const rows = await db
    .select()
    .from(subscriptions)
    .where(
      and(
        eq(subscriptions.userId, userId),
        eq(subscriptions.status, "active"),
      ),
    )
    .limit(1);

  return rows[0] ?? null;
}

/** Insert or update a subscription by stripeSubscriptionId. */
export async function upsertSubscription(data: {
  userId: string;
  stripeCustomerId: string;
  stripeSubscriptionId: string;
  stripePriceId: string;
  planId: string;
  status: SubscriptionStatus;
  currentPeriodStart?: Date;
  currentPeriodEnd?: Date;
}) {
  const existing = await db
    .select({ id: subscriptions.id })
    .from(subscriptions)
    .where(eq(subscriptions.stripeSubscriptionId, data.stripeSubscriptionId))
    .limit(1);

  if (existing.length > 0) {
    const [updated] = await db
      .update(subscriptions)
      .set({ ...data, updatedAt: new Date() })
      .where(eq(subscriptions.id, existing[0].id))
      .returning();
    return updated;
  }

  const [inserted] = await db.insert(subscriptions).values(data).returning();
  return inserted;
}

/** Update only the status of a subscription by stripeSubscriptionId. */
export async function updateSubscriptionStatus(
  stripeSubscriptionId: string,
  status: SubscriptionStatus,
) {
  await db
    .update(subscriptions)
    .set({ status, updatedAt: new Date() })
    .where(eq(subscriptions.stripeSubscriptionId, stripeSubscriptionId));
}

/* ─────────────────────────────────────────────────────────
 * Repositories
 * ───────────────────────────────────────────────────────── */

/** Inferred repository row type. */
export type RepositoryRow = typeof repositories.$inferSelect;

/** List connected repositories for a user. */
export async function getRepositories(
  userId: string,
): Promise<RepositoryRow[]> {
  return db
    .select()
    .from(repositories)
    .where(eq(repositories.userId, userId))
    .orderBy(desc(repositories.createdAt));
}

/* ─────────────────────────────────────────────────────────
 * Upsert outcome
 * ───────────────────────────────────────────────────────── */

/** Data needed to insert or update an agent outcome. */
export interface UpsertOutcomeData {
  userId: string;
  outcome: OutcomeValue;
  prUrl: string;
  prNumber: number;
  branch: string;
  riskTier: RiskTier;
  checksGate?: CheckStatus;
  checksTests?: CheckStatus;
  checksReview?: CheckStatus;
  checksSpecAudit?: CheckStatus;
  filesChanged?: string[];
  reviewFindings?: string[];
  runId?: string;
  model?: string;
  reviewModel?: string;
  provider?: string;
  engine?: string;
  costUsd?: string;
  durationMs?: number;
  numTurns?: number;
  timestamp?: Date;
}

/** Insert or update an outcome record. Upserts on runId if provided. */
export async function upsertOutcome(
  data: UpsertOutcomeData,
): Promise<OutcomeRow> {
  const values = {
    userId: data.userId,
    outcome: data.outcome,
    prUrl: data.prUrl,
    prNumber: data.prNumber,
    branch: data.branch,
    riskTier: data.riskTier,
    checksGate: data.checksGate ?? null,
    checksTests: data.checksTests ?? null,
    checksReview: data.checksReview ?? null,
    checksSpecAudit: data.checksSpecAudit ?? null,
    filesChanged: data.filesChanged ?? [],
    reviewFindings: data.reviewFindings ?? [],
    runId: data.runId ?? null,
    model: data.model ?? null,
    reviewModel: data.reviewModel ?? null,
    provider: data.provider ?? null,
    engine: data.engine ?? null,
    costUsd: data.costUsd ?? null,
    durationMs: data.durationMs ?? null,
    numTurns: data.numTurns ?? null,
    timestamp: data.timestamp ?? new Date(),
  };

  // If runId is provided, upsert on it; otherwise just insert.
  if (data.runId) {
    const existing = await db
      .select({ id: agentOutcomes.id })
      .from(agentOutcomes)
      .where(
        and(
          eq(agentOutcomes.userId, data.userId),
          eq(agentOutcomes.runId, data.runId),
        ),
      )
      .limit(1);

    if (existing.length > 0) {
      const [updated] = await db
        .update(agentOutcomes)
        .set(values)
        .where(eq(agentOutcomes.id, existing[0].id))
        .returning();
      return updated;
    }
  }

  const [inserted] = await db
    .insert(agentOutcomes)
    .values(values)
    .returning();
  return inserted;
}

/* ─────────────────────────────────────────────────────────
 * Chat sessions & messages
 * ───────────────────────────────────────────────────────── */

/** Inferred chat session row type. */
export type ChatSessionRow = typeof chatSessions.$inferSelect;

/** Inferred chat message row type. */
export type ChatMessageRow = typeof chatMessages.$inferSelect;

/** Fetch recent chat sessions for a user. */
export async function getChatSessions(
  userId: string,
  limit: number = 20,
): Promise<ChatSessionRow[]> {
  return db
    .select()
    .from(chatSessions)
    .where(eq(chatSessions.userId, userId))
    .orderBy(desc(chatSessions.updatedAt))
    .limit(limit);
}

/** Fetch all messages in a chat session, ordered chronologically. */
export async function getChatMessages(
  sessionId: string,
): Promise<ChatMessageRow[]> {
  return db
    .select()
    .from(chatMessages)
    .where(eq(chatMessages.sessionId, sessionId))
    .orderBy(asc(chatMessages.createdAt));
}

/** Get the most recent chat session for a user, or create one if none exists. */
export async function getOrCreateChatSession(
  userId: string,
): Promise<ChatSessionRow> {
  const existing = await db
    .select()
    .from(chatSessions)
    .where(eq(chatSessions.userId, userId))
    .orderBy(desc(chatSessions.updatedAt))
    .limit(1);

  if (existing.length > 0) {
    return existing[0];
  }

  const [created] = await db
    .insert(chatSessions)
    .values({ userId })
    .returning();
  return created;
}

/** Save a chat message and update the session's updatedAt timestamp. */
export async function saveChatMessage(data: {
  sessionId: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata?: Record<string, unknown>;
}): Promise<ChatMessageRow> {
  const [message] = await db
    .insert(chatMessages)
    .values({
      sessionId: data.sessionId,
      role: data.role,
      content: data.content,
      metadata: data.metadata ?? null,
    })
    .returning();

  await db
    .update(chatSessions)
    .set({ updatedAt: new Date() })
    .where(eq(chatSessions.id, data.sessionId));

  return message;
}
