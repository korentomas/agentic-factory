import { promises as fs } from "fs";
import path from "path";
import type {
  AgentOutcome,
  CheckHealth,
  DashboardStats,
  EngineBreakdown,
  FileHotspot,
  ModelBreakdown,
  RiskBreakdown,
} from "./types";

const OUTCOMES_PATH = path.join(
  process.cwd(),
  "..",
  "data",
  "agent-outcomes.jsonl"
);

/** Read and parse the agent outcomes JSONL file. */
export async function loadOutcomes(): Promise<AgentOutcome[]> {
  try {
    const raw = await fs.readFile(OUTCOMES_PATH, "utf-8");
    return raw
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => JSON.parse(line) as AgentOutcome);
  } catch {
    return [];
  }
}

/** Compute high-level dashboard stats from outcomes. */
export function computeStats(outcomes: AgentOutcome[]): DashboardStats {
  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1);

  const thisMonth = outcomes.filter(
    (o) => new Date(o.timestamp) >= monthStart
  );
  const clean = outcomes.filter((o) => o.outcome === "clean");
  const failed = outcomes.filter((o) => o.outcome !== "clean");

  const totalCost = outcomes.reduce((sum, o) => sum + (o.cost_usd ?? 0), 0);
  const monthCost = thisMonth.reduce((sum, o) => sum + (o.cost_usd ?? 0), 0);

  const durations = outcomes.filter((o) => o.duration_ms).map((o) => o.duration_ms!);
  const avgDuration =
    durations.length > 0
      ? durations.reduce((a, b) => a + b, 0) / durations.length
      : 0;

  return {
    totalTasks: outcomes.length,
    tasksThisMonth: thisMonth.length,
    prsShipped: clean.length,
    prsClean: clean.length,
    prsFailed: failed.length,
    successRate: outcomes.length > 0 ? clean.length / outcomes.length : 0,
    totalCost,
    costThisMonth: monthCost,
    avgDurationMs: avgDuration,
  };
}

/** Group outcomes by engine and compute per-engine metrics. */
export function computeEngineBreakdown(
  outcomes: AgentOutcome[]
): EngineBreakdown[] {
  const groups = new Map<string, AgentOutcome[]>();

  for (const o of outcomes) {
    const engine = o.engine || "claude-code";
    const list = groups.get(engine) || [];
    list.push(o);
    groups.set(engine, list);
  }

  return Array.from(groups.entries()).map(([engine, items]) => {
    const successCount = items.filter((o) => o.outcome === "clean").length;
    const costs = items.filter((o) => o.cost_usd).map((o) => o.cost_usd!);
    const durations = items
      .filter((o) => o.duration_ms)
      .map((o) => o.duration_ms!);

    return {
      engine,
      count: items.length,
      successCount,
      failureCount: items.length - successCount,
      successRate: items.length > 0 ? successCount / items.length : 0,
      avgCost: costs.length > 0 ? costs.reduce((a, b) => a + b, 0) / costs.length : 0,
      avgDuration:
        durations.length > 0
          ? durations.reduce((a, b) => a + b, 0) / durations.length
          : 0,
    };
  });
}

/** Group outcomes by model and compute per-model metrics. */
export function computeModelBreakdown(
  outcomes: AgentOutcome[]
): ModelBreakdown[] {
  const groups = new Map<string, AgentOutcome[]>();

  for (const o of outcomes) {
    const model = o.model || "unknown";
    const list = groups.get(model) || [];
    list.push(o);
    groups.set(model, list);
  }

  return Array.from(groups.entries()).map(([model, items]) => {
    const successCount = items.filter((o) => o.outcome === "clean").length;
    const stages = [
      ...new Set(items.flatMap((o) => (o.review_model ? ["write", "review"] : ["write"]))),
    ];

    return {
      model,
      count: items.length,
      successCount,
      failureCount: items.length - successCount,
      successRate: items.length > 0 ? successCount / items.length : 0,
      stages,
    };
  });
}

/** Compute check pass rates across all outcomes. */
export function computeCheckHealth(outcomes: AgentOutcome[]): CheckHealth[] {
  const checks: (keyof AgentOutcome["checks"])[] = [
    "gate",
    "tests",
    "review",
    "spec_audit",
  ];

  return checks.map((name) => {
    let passed = 0;
    let failed = 0;
    let skipped = 0;

    for (const o of outcomes) {
      const val = o.checks[name];
      if (val === "success") passed++;
      else if (val === "failure") failed++;
      else skipped++;
    }

    const evaluated = passed + failed;
    return {
      name: name === "spec_audit" ? "Spec Audit" : name.charAt(0).toUpperCase() + name.slice(1),
      passed,
      failed,
      skipped,
      passRate: evaluated > 0 ? passed / evaluated : 0,
    };
  });
}

/** Group outcomes by risk tier. */
export function computeRiskBreakdown(
  outcomes: AgentOutcome[]
): RiskBreakdown[] {
  const tiers: AgentOutcome["risk_tier"][] = ["high", "medium", "low"];

  return tiers.map((tier) => {
    const items = outcomes.filter((o) => o.risk_tier === tier);
    const successCount = items.filter((o) => o.outcome === "clean").length;

    return {
      tier,
      count: items.length,
      successCount,
      failureCount: items.length - successCount,
      successRate: items.length > 0 ? successCount / items.length : 0,
    };
  }).filter((r) => r.count > 0);
}

/** Find most-changed files across outcomes. */
export function computeFileHotspots(
  outcomes: AgentOutcome[]
): FileHotspot[] {
  const fileMap = new Map<
    string,
    { appearances: number; inSuccessful: number; inFailed: number }
  >();

  for (const o of outcomes) {
    for (const f of o.files_changed) {
      const entry = fileMap.get(f) || {
        appearances: 0,
        inSuccessful: 0,
        inFailed: 0,
      };
      entry.appearances++;
      if (o.outcome === "clean") entry.inSuccessful++;
      else entry.inFailed++;
      fileMap.set(f, entry);
    }
  }

  return Array.from(fileMap.entries())
    .map(([filePath, data]) => ({ path: filePath, ...data }))
    .sort((a, b) => b.appearances - a.appearances)
    .slice(0, 20);
}
