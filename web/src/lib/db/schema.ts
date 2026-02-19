import {
  boolean,
  index,
  integer,
  json,
  numeric,
  pgTable,
  primaryKey,
  text,
  timestamp,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

/* ─────────────────────────────────────────────────────────
 * NextAuth tables — custom schema with snake_case DB columns
 * Property names (camelCase) match what @auth/drizzle-adapter expects.
 * DB column names (snake_case) match our convention.
 * ───────────────────────────────────────────────────────── */

/** Users table — NextAuth compatible. */
export const users = pgTable("users", {
  id: text("id")
    .primaryKey()
    .$defaultFn(() => crypto.randomUUID()),
  name: text("name"),
  email: text("email").unique(),
  emailVerified: timestamp("email_verified", { mode: "date" }),
  image: text("image"),
  createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
});

/** Accounts table — NextAuth compatible (OAuth provider links). */
export const accounts = pgTable(
  "accounts",
  {
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    type: text("type").$type<"oauth" | "oidc" | "email" | "webauthn">().notNull(),
    provider: text("provider").notNull(),
    providerAccountId: text("provider_account_id").notNull(),
    refresh_token: text("refresh_token"),
    access_token: text("access_token"),
    expires_at: integer("expires_at"),
    token_type: text("token_type"),
    scope: text("scope"),
    id_token: text("id_token"),
    session_state: text("session_state"),
  },
  (account) => [
    primaryKey({ columns: [account.provider, account.providerAccountId] }),
    index("accounts_user_id_idx").on(account.userId),
  ],
);

/** Sessions table — NextAuth compatible. */
export const sessions = pgTable(
  "sessions",
  {
    sessionToken: text("session_token").primaryKey(),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    expires: timestamp("expires", { mode: "date" }).notNull(),
  },
  (session) => [
    index("sessions_user_id_idx").on(session.userId),
  ],
);

/** Verification tokens — NextAuth compatible (email verification, etc). */
export const verificationTokens = pgTable(
  "verification_tokens",
  {
    identifier: text("identifier").notNull(),
    token: text("token").notNull(),
    expires: timestamp("expires", { mode: "date" }).notNull(),
  },
  (vt) => [
    primaryKey({ columns: [vt.identifier, vt.token] }),
  ],
);

/* ─────────────────────────────────────────────────────────
 * Application tables
 * ───────────────────────────────────────────────────────── */

/** Subscription statuses for Stripe. */
export type SubscriptionStatus =
  | "active"
  | "cancelled"
  | "past_due"
  | "trialing";

/** Subscriptions table — Stripe subscription data. */
export const subscriptions = pgTable(
  "subscriptions",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    stripeCustomerId: text("stripe_customer_id").notNull(),
    stripeSubscriptionId: text("stripe_subscription_id").unique(),
    stripePriceId: text("stripe_price_id"),
    planId: text("plan_id").notNull(),
    status: text("status")
      .$type<SubscriptionStatus>()
      .notNull()
      .default("active"),
    currentPeriodStart: timestamp("current_period_start", { mode: "date" }),
    currentPeriodEnd: timestamp("current_period_end", { mode: "date" }),
    cancelAtPeriodEnd: boolean("cancel_at_period_end").notNull().default(false),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { mode: "date" }).notNull().defaultNow(),
  },
  (sub) => [
    index("subscriptions_user_id_idx").on(sub.userId),
    index("subscriptions_stripe_customer_id_idx").on(sub.stripeCustomerId),
    index("subscriptions_stripe_subscription_id_idx").on(
      sub.stripeSubscriptionId,
    ),
  ],
);

/** Outcome values matching the pipeline spec. */
export type OutcomeValue =
  | "clean"
  | "tests-failed"
  | "review-failed"
  | "blocked";

/** Check status values. */
export type CheckStatus = "success" | "failure" | "skipped";

/** Risk tier values. */
export type RiskTier = "high" | "medium" | "low";

/** Agent outcomes table — mirrors agent-outcomes.jsonl in the database. */
export const agentOutcomes = pgTable(
  "agent_outcomes",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    outcome: text("outcome").$type<OutcomeValue>().notNull(),
    prUrl: text("pr_url").notNull(),
    prNumber: integer("pr_number").notNull(),
    branch: text("branch").notNull(),
    riskTier: text("risk_tier").$type<RiskTier>().notNull(),
    checksGate: text("checks_gate").$type<CheckStatus>(),
    checksTests: text("checks_tests").$type<CheckStatus>(),
    checksReview: text("checks_review").$type<CheckStatus>(),
    checksSpecAudit: text("checks_spec_audit").$type<CheckStatus>(),
    filesChanged: json("files_changed").$type<string[]>().default([]),
    reviewFindings: json("review_findings").$type<string[]>().default([]),
    runId: text("run_id"),
    model: text("model"),
    reviewModel: text("review_model"),
    provider: text("provider"),
    engine: text("engine"),
    costUsd: numeric("cost_usd", { precision: 10, scale: 4 }),
    durationMs: integer("duration_ms"),
    numTurns: integer("num_turns"),
    timestamp: timestamp("timestamp", { mode: "date" }).notNull().defaultNow(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
  },
  (outcome) => [
    index("agent_outcomes_user_id_idx").on(outcome.userId),
    index("agent_outcomes_outcome_idx").on(outcome.outcome),
    index("agent_outcomes_timestamp_idx").on(outcome.timestamp),
    index("agent_outcomes_run_id_idx").on(outcome.runId),
    index("agent_outcomes_engine_idx").on(outcome.engine),
    index("agent_outcomes_model_idx").on(outcome.model),
    index("agent_outcomes_risk_tier_idx").on(outcome.riskTier),
  ],
);

/** Repositories table — connected GitHub repos. */
export const repositories = pgTable(
  "repositories",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    githubRepoId: integer("github_repo_id").notNull(),
    fullName: text("full_name").notNull(),
    installationId: integer("installation_id").notNull(),
    isActive: boolean("is_active").notNull().default(true),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
  },
  (repo) => [
    index("repositories_user_id_idx").on(repo.userId),
    index("repositories_github_repo_id_idx").on(repo.githubRepoId),
    index("repositories_installation_id_idx").on(repo.installationId),
  ],
);

/** Chat sessions. */
export const chatSessions = pgTable(
  "chat_sessions",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
    repositoryId: text("repository_id").references(() => repositories.id, { onDelete: "set null" }),
    title: text("title"),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { mode: "date" }).notNull().defaultNow(),
  },
  (session) => [
    index("chat_sessions_user_id_idx").on(session.userId),
    index("chat_sessions_updated_at_idx").on(session.updatedAt),
  ],
);

/** Chat messages. */
export const chatMessages = pgTable(
  "chat_messages",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    sessionId: text("session_id").notNull().references(() => chatSessions.id, { onDelete: "cascade" }),
    role: text("role").$type<"user" | "assistant" | "system">().notNull(),
    content: text("content").notNull(),
    metadata: json("metadata").$type<Record<string, unknown>>(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
  },
  (msg) => [
    index("chat_messages_session_id_idx").on(msg.sessionId),
    index("chat_messages_created_at_idx").on(msg.createdAt),
  ],
);

/* ─────────────────────────────────────────────────────────
 * Task execution tables (Open SWE-style)
 * ───────────────────────────────────────────────────────── */

/** Task thread status values. */
export type TaskThreadStatus =
  | "pending"
  | "running"
  | "committing"
  | "complete"
  | "failed"
  | "cancelled";

/** Task threads — one per agent execution. */
export const taskThreads = pgTable(
  "task_threads",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    repoUrl: text("repo_url").notNull(),
    branch: text("branch").notNull(),
    baseBranch: text("base_branch").notNull().default("main"),
    title: text("title").notNull(),
    description: text("description").notNull(),
    status: text("status").$type<TaskThreadStatus>().notNull().default("pending"),
    engine: text("engine"),
    model: text("model"),
    riskTier: text("risk_tier").$type<RiskTier>().default("medium"),
    costUsd: numeric("cost_usd", { precision: 10, scale: 4 }).default("0"),
    numTurns: integer("num_turns").default(0),
    durationMs: integer("duration_ms").default(0),
    commitSha: text("commit_sha"),
    errorMessage: text("error_message"),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
    updatedAt: timestamp("updated_at", { mode: "date" }).notNull().defaultNow(),
  },
  (thread) => [
    index("task_threads_user_id_idx").on(thread.userId),
    index("task_threads_status_idx").on(thread.status),
    index("task_threads_created_at_idx").on(thread.createdAt),
  ],
);

/** Message role within a task execution. */
export type TaskMessageRole =
  | "human"
  | "assistant"
  | "tool"
  | "system"
  | "manager";

/** Task messages — streaming events within a thread. */
export const taskMessages = pgTable(
  "task_messages",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    threadId: text("thread_id")
      .notNull()
      .references(() => taskThreads.id, { onDelete: "cascade" }),
    role: text("role").$type<TaskMessageRole>().notNull(),
    content: text("content"),
    toolName: text("tool_name"),
    toolInput: text("tool_input"),
    toolOutput: text("tool_output"),
    metadata: json("metadata").$type<Record<string, unknown>>(),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
  },
  (msg) => [
    index("task_messages_thread_id_idx").on(msg.threadId),
    index("task_messages_created_at_idx").on(msg.createdAt),
  ],
);

/** Task plan step status. */
export type TaskPlanStepStatus = "pending" | "in_progress" | "completed" | "skipped";

/** Task plans — agent execution plans with revisions. */
export const taskPlans = pgTable(
  "task_plans",
  {
    id: text("id").primaryKey().$defaultFn(() => crypto.randomUUID()),
    threadId: text("thread_id")
      .notNull()
      .references(() => taskThreads.id, { onDelete: "cascade" }),
    revision: integer("revision").notNull().default(1),
    steps: json("steps").$type<Array<{
      title: string;
      description: string;
      status: TaskPlanStepStatus;
    }>>().notNull(),
    createdBy: text("created_by").default("agent"),
    createdAt: timestamp("created_at", { mode: "date" }).notNull().defaultNow(),
  },
  (plan) => [
    index("task_plans_thread_id_idx").on(plan.threadId),
  ],
);

/* ─────────────────────────────────────────────────────────
 * Relations
 * ───────────────────────────────────────────────────────── */

export const usersRelations = relations(users, ({ many }) => ({
  accounts: many(accounts),
  sessions: many(sessions),
  subscriptions: many(subscriptions),
  agentOutcomes: many(agentOutcomes),
  repositories: many(repositories),
  chatSessions: many(chatSessions),
  taskThreads: many(taskThreads),
}));

export const accountsRelations = relations(accounts, ({ one }) => ({
  user: one(users, {
    fields: [accounts.userId],
    references: [users.id],
  }),
}));

export const sessionsRelations = relations(sessions, ({ one }) => ({
  user: one(users, {
    fields: [sessions.userId],
    references: [users.id],
  }),
}));

export const subscriptionsRelations = relations(subscriptions, ({ one }) => ({
  user: one(users, {
    fields: [subscriptions.userId],
    references: [users.id],
  }),
}));

export const agentOutcomesRelations = relations(agentOutcomes, ({ one }) => ({
  user: one(users, {
    fields: [agentOutcomes.userId],
    references: [users.id],
  }),
}));

export const repositoriesRelations = relations(repositories, ({ one }) => ({
  user: one(users, {
    fields: [repositories.userId],
    references: [users.id],
  }),
}));

export const chatSessionsRelations = relations(chatSessions, ({ one, many }) => ({
  user: one(users, {
    fields: [chatSessions.userId],
    references: [users.id],
  }),
  repository: one(repositories, {
    fields: [chatSessions.repositoryId],
    references: [repositories.id],
  }),
  messages: many(chatMessages),
}));

export const chatMessagesRelations = relations(chatMessages, ({ one }) => ({
  session: one(chatSessions, {
    fields: [chatMessages.sessionId],
    references: [chatSessions.id],
  }),
}));

export const taskThreadsRelations = relations(taskThreads, ({ one, many }) => ({
  user: one(users, {
    fields: [taskThreads.userId],
    references: [users.id],
  }),
  messages: many(taskMessages),
  plans: many(taskPlans),
}));

export const taskMessagesRelations = relations(taskMessages, ({ one }) => ({
  thread: one(taskThreads, {
    fields: [taskMessages.threadId],
    references: [taskThreads.id],
  }),
}));

export const taskPlansRelations = relations(taskPlans, ({ one }) => ({
  thread: one(taskThreads, {
    fields: [taskPlans.threadId],
    references: [taskThreads.id],
  }),
}));
