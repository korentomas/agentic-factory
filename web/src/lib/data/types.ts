/* ── Dashboard data types ── */

export interface OutcomeChecks {
  gate: "success" | "failure" | "skipped";
  tests: "success" | "failure" | "skipped";
  review: "success" | "failure" | "skipped";
  spec_audit: "success" | "failure" | "skipped";
}

export interface AgentOutcome {
  outcome: "clean" | "tests-failed" | "review-failed" | "blocked";
  pr_url: string;
  pr_number: number;
  branch: string;
  risk_tier: "high" | "medium" | "low";
  checks: OutcomeChecks;
  files_changed: string[];
  review_findings: string[];
  run_id: string;
  timestamp: string;
  model?: string;
  review_model?: string;
  provider?: string;
  cost_usd?: number;
  duration_ms?: number;
  engine?: string;
  num_turns?: number;
}

export interface DashboardStats {
  totalTasks: number;
  tasksThisMonth: number;
  prsShipped: number;
  prsClean: number;
  prsFailed: number;
  successRate: number;
  totalCost: number;
  costThisMonth: number;
  avgDurationMs: number;
}

export interface EngineBreakdown {
  engine: string;
  count: number;
  successCount: number;
  failureCount: number;
  successRate: number;
  avgCost: number;
  avgDuration: number;
}

export interface ModelBreakdown {
  model: string;
  count: number;
  successCount: number;
  failureCount: number;
  successRate: number;
  stages: string[];
}

export interface CheckHealth {
  name: string;
  passed: number;
  failed: number;
  skipped: number;
  passRate: number;
}

export interface RiskBreakdown {
  tier: "high" | "medium" | "low";
  count: number;
  successCount: number;
  failureCount: number;
  successRate: number;
}

export interface FileHotspot {
  path: string;
  appearances: number;
  inSuccessful: number;
  inFailed: number;
}

export interface LearnedPattern {
  kind: "pattern" | "anti-pattern";
  description: string;
  evidenceCount: number;
  confidence: number;
  riskTier?: string;
}

export interface LearningStats {
  totalOutcomes: number;
  patternsDiscovered: number;
  antiPatternsDiscovered: number;
  patterns: LearnedPattern[];
  lastExtractionDate: string | null;
  nextExtractionEligible: boolean;
}

export interface PRDetail {
  number: number;
  url: string;
  title: string;
  state: "open" | "closed" | "merged";
  branch: string;
  outcome: AgentOutcome["outcome"];
  riskTier: AgentOutcome["risk_tier"];
  engine: string;
  model: string;
  cost: number;
  duration: number;
  numTurns: number;
  filesChanged: string[];
  checksStatus: OutcomeChecks;
  timestamp: string;
  mergedAt: string | null;
}

export interface CodeRetention {
  prNumber: number;
  prUrl: string;
  filesChanged: string[];
  linesWritten: number;
  linesRetained: number;
  linesOverwritten: number;
  overwrittenByAgent: number;
  overwrittenByHuman: number;
  retentionRate: number;
}

export interface DashboardData {
  stats: DashboardStats;
  outcomes: AgentOutcome[];
  prs: PRDetail[];
  engines: EngineBreakdown[];
  models: ModelBreakdown[];
  checks: CheckHealth[];
  risks: RiskBreakdown[];
  fileHotspots: FileHotspot[];
  learning: LearningStats;
  codeRetention: CodeRetention[];
}
