import { promises as fs } from "fs";
import path from "path";
import type { LearnedPattern, LearningStats } from "./types";

const RULES_DIR = path.join(process.cwd(), "..", ".claude", "rules");

/** Parse learned patterns from rules markdown files. */
export async function loadLearningStats(
  totalOutcomes: number
): Promise<LearningStats> {
  const patterns: LearnedPattern[] = [];
  let lastExtraction: string | null = null;

  try {
    const patternsContent = await fs.readFile(
      path.join(RULES_DIR, "patterns.md"),
      "utf-8"
    );
    patterns.push(...parsePatternsMd(patternsContent, "pattern"));
  } catch {
    /* no patterns file */
  }

  try {
    const antiContent = await fs.readFile(
      path.join(RULES_DIR, "anti-patterns.md"),
      "utf-8"
    );
    patterns.push(...parsePatternsMd(antiContent, "anti-pattern"));
  } catch {
    /* no anti-patterns file */
  }

  // Check for last extraction date from git or file mtime
  try {
    const stat = await fs.stat(path.join(RULES_DIR, "patterns.md"));
    lastExtraction = stat.mtime.toISOString();
  } catch {
    /* no file */
  }

  const patternCount = patterns.filter((p) => p.kind === "pattern").length;
  const antiPatternCount = patterns.filter(
    (p) => p.kind === "anti-pattern"
  ).length;

  // Pattern extraction needs 3+ successful PRs for patterns, 2+ failures for anti-patterns
  const successCount = totalOutcomes; // approximate; caller can provide accurate count
  const nextEligible = successCount >= 3;

  return {
    totalOutcomes,
    patternsDiscovered: patternCount,
    antiPatternsDiscovered: antiPatternCount,
    patterns,
    lastExtractionDate: lastExtraction,
    nextExtractionEligible: nextEligible,
  };
}

/** Parse patterns or anti-patterns from a rules markdown file. */
function parsePatternsMd(
  content: string,
  kind: "pattern" | "anti-pattern"
): LearnedPattern[] {
  const patterns: LearnedPattern[] = [];
  const lines = content.split("\n");

  // Extract header stats (e.g., "Based on 1 runs. Success rate: 100%.")
  let evidenceCount = 0;
  let confidence = 0;

  for (const line of lines) {
    const runsMatch = line.match(/Based on (\d+) runs/);
    if (runsMatch) {
      evidenceCount = parseInt(runsMatch[1], 10);
    }

    const rateMatch = line.match(/Success rate: ([\d.]+)%/);
    if (rateMatch) {
      confidence = parseFloat(rateMatch[1]) / 100;
    }

    // Parse bullet items as individual patterns
    const bulletMatch = line.match(/^- \*\*(.+?)\*\*[: ]+(.+)/);
    if (bulletMatch) {
      patterns.push({
        kind,
        description: `${bulletMatch[1]}: ${bulletMatch[2]}`,
        evidenceCount,
        confidence,
        riskTier: bulletMatch[1].toLowerCase(),
      });
    }
  }

  // If "No recurring anti-patterns detected yet" type message, return empty
  if (
    content.includes("No recurring") ||
    content.includes("not detected") ||
    content.includes("no data")
  ) {
    return [];
  }

  return patterns;
}
