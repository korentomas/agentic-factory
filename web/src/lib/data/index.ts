import type { DashboardData } from "./types";
import {
  loadOutcomes,
  computeStats,
  computeEngineBreakdown,
  computeModelBreakdown,
  computeCheckHealth,
  computeRiskBreakdown,
  computeFileHotspots,
} from "./outcomes";
import { loadLearningStats } from "./patterns";
import { fetchPRDetails, fetchCodeRetention } from "./github";

export type { DashboardData } from "./types";

/** Load all dashboard data from outcomes file, rules, and GitHub API. */
export async function loadDashboardData(
  accessToken?: string
): Promise<DashboardData> {
  const outcomes = await loadOutcomes();
  const stats = computeStats(outcomes);

  // Fetch PR details from GitHub (with fallback to outcome-only data)
  const prs = await fetchPRDetails(outcomes, accessToken);

  // Compute code retention for merged PRs
  const codeRetention = await fetchCodeRetention(prs, accessToken);

  // Load self-learning stats
  const learning = await loadLearningStats(outcomes.length);

  return {
    stats,
    outcomes,
    prs,
    engines: computeEngineBreakdown(outcomes),
    models: computeModelBreakdown(outcomes),
    checks: computeCheckHealth(outcomes),
    risks: computeRiskBreakdown(outcomes),
    fileHotspots: computeFileHotspots(outcomes),
    learning,
    codeRetention,
  };
}
