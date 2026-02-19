import { describe, it, expect, vi, beforeEach } from "vitest";

const { mockReadFile, mockStat } = vi.hoisted(() => ({
  mockReadFile: vi.fn(),
  mockStat: vi.fn(),
}));

// Mock fs module before importing the module under test
vi.mock("fs", () => {
  const mockPromises = { readFile: mockReadFile, stat: mockStat };
  return {
    default: { promises: mockPromises },
    promises: mockPromises,
  };
});

import { loadLearningStats } from "../patterns";

/**
 * Helper to create a mockReadFile implementation that dispatches based on path.
 * IMPORTANT: check anti-patterns.md BEFORE patterns.md since the former is a
 * substring of the latter.
 */
function mockFileContents(
  patternsContent: string | null,
  antiPatternsContent: string | null
): void {
  mockReadFile.mockImplementation((filePath: unknown) => {
    const p = String(filePath);
    // Check anti-patterns.md first (it contains "patterns.md" as a substring)
    if (p.includes("anti-patterns.md")) {
      if (antiPatternsContent !== null) return Promise.resolve(antiPatternsContent);
      return Promise.reject(new Error("ENOENT"));
    }
    if (p.includes("patterns.md")) {
      if (patternsContent !== null) return Promise.resolve(patternsContent);
      return Promise.reject(new Error("ENOENT"));
    }
    return Promise.reject(new Error("ENOENT"));
  });
}

describe("loadLearningStats", () => {
  beforeEach(() => {
    vi.resetAllMocks();
  });

  it("parses patterns from real markdown content", async () => {
    const patternsContent = `# Agent Patterns — What Works Well

Based on 5 runs. Success rate: 80%.

- **medium** risk: 80% success rate
- **low** risk: 100% success rate
`;
    const antiPatternsContent = `# Agent Anti-Patterns — Watch Out For

Based on 3 runs. Success rate: 33%.

- **bare-except** catch: Causes silent failures in production
`;
    const mockMtime = new Date("2026-01-15T10:00:00Z");

    mockFileContents(patternsContent, antiPatternsContent);
    mockStat.mockResolvedValue({ mtime: mockMtime });

    const stats = await loadLearningStats(10);

    expect(stats.totalOutcomes).toBe(10);
    expect(stats.patternsDiscovered).toBe(2);
    expect(stats.antiPatternsDiscovered).toBe(1);
    expect(stats.patterns).toHaveLength(3);
    expect(stats.lastExtractionDate).toBe(mockMtime.toISOString());
    expect(stats.nextExtractionEligible).toBe(true);
  });

  it("returns empty patterns when no files exist", async () => {
    mockReadFile.mockRejectedValue(new Error("ENOENT"));
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(0);

    expect(stats.patternsDiscovered).toBe(0);
    expect(stats.antiPatternsDiscovered).toBe(0);
    expect(stats.patterns).toEqual([]);
    expect(stats.lastExtractionDate).toBeNull();
  });

  it("handles patterns file only (no anti-patterns file)", async () => {
    const patternsContent = `# Agent Patterns

Based on 2 runs. Success rate: 100%.

- **low** risk: 100% success rate
`;
    const mockMtime = new Date("2026-02-01T12:00:00Z");

    mockFileContents(patternsContent, null);
    mockStat.mockResolvedValue({ mtime: mockMtime });

    const stats = await loadLearningStats(5);

    expect(stats.patternsDiscovered).toBe(1);
    expect(stats.antiPatternsDiscovered).toBe(0);
  });

  it("handles anti-patterns file only (no patterns file)", async () => {
    const antiContent = `# Agent Anti-Patterns

Based on 2 runs. Success rate: 50%.

- **timeout** handling: Missing timeout on external API calls
`;

    mockFileContents(null, antiContent);
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(4);

    expect(stats.patternsDiscovered).toBe(0);
    expect(stats.antiPatternsDiscovered).toBe(1);
    expect(stats.lastExtractionDate).toBeNull();
  });

  it("detects 'No recurring' message and returns empty anti-patterns", async () => {
    const patternsContent = `# Agent Patterns

Based on 1 runs. Success rate: 100%.

- **medium** risk: 100% success rate
`;
    const antiContent = `# Agent Anti-Patterns — Watch Out For

No recurring anti-patterns detected yet.
`;
    const mockMtime = new Date("2026-01-20T08:00:00Z");

    mockFileContents(patternsContent, antiContent);
    mockStat.mockResolvedValue({ mtime: mockMtime });

    const stats = await loadLearningStats(5);

    expect(stats.patternsDiscovered).toBe(1);
    expect(stats.antiPatternsDiscovered).toBe(0);
  });

  it("handles 'not detected' message", async () => {
    const antiContent = `# Anti-Patterns

Errors not detected in recent runs.
`;

    mockFileContents(null, antiContent);
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(1);

    expect(stats.antiPatternsDiscovered).toBe(0);
  });

  it("handles 'no data' message", async () => {
    const patternsContent = `# Patterns

There is no data to analyze yet.
`;

    mockFileContents(patternsContent, null);
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(0);

    expect(stats.patternsDiscovered).toBe(0);
  });

  it("extracts evidence count from 'Based on N runs'", async () => {
    const patternsContent = `# Agent Patterns

Based on 12 runs. Success rate: 75%.

- **high** risk: 50% success rate
`;
    mockFileContents(patternsContent, null);
    mockStat.mockResolvedValue({ mtime: new Date() });

    const stats = await loadLearningStats(12);

    const highPattern = stats.patterns.find((p) => p.riskTier === "high");
    expect(highPattern).toBeDefined();
    expect(highPattern!.evidenceCount).toBe(12);
  });

  it("extracts confidence from 'Success rate: N%'", async () => {
    const patternsContent = `# Agent Patterns

Based on 8 runs. Success rate: 87.5%.

- **medium** risk: 87.5% success rate
`;
    mockFileContents(patternsContent, null);
    mockStat.mockResolvedValue({ mtime: new Date() });

    const stats = await loadLearningStats(8);

    const pattern = stats.patterns[0];
    expect(pattern.confidence).toBeCloseTo(0.875, 3);
  });

  it("sets nextExtractionEligible to true when totalOutcomes >= 3", async () => {
    mockReadFile.mockRejectedValue(new Error("ENOENT"));
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(3);
    expect(stats.nextExtractionEligible).toBe(true);
  });

  it("sets nextExtractionEligible to false when totalOutcomes < 3", async () => {
    mockReadFile.mockRejectedValue(new Error("ENOENT"));
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(2);
    expect(stats.nextExtractionEligible).toBe(false);
  });

  it("parses multiple bullet items from a single file", async () => {
    const patternsContent = `# Agent Patterns

Based on 10 runs. Success rate: 90%.

- **low** risk: 95% success rate
- **medium** risk: 85% success rate
- **high** risk: 70% success rate
`;
    mockFileContents(patternsContent, null);
    mockStat.mockResolvedValue({ mtime: new Date() });

    const stats = await loadLearningStats(10);

    expect(stats.patternsDiscovered).toBe(3);
    expect(stats.patterns).toHaveLength(3);
    expect(stats.patterns.map((p) => p.riskTier)).toEqual(["low", "medium", "high"]);
  });

  it("sets kind to 'pattern' for patterns file entries", async () => {
    const patternsContent = `# Patterns
Based on 1 runs. Success rate: 100%.
- **low** risk: all passing
`;
    mockFileContents(patternsContent, null);
    mockStat.mockResolvedValue({ mtime: new Date() });

    const stats = await loadLearningStats(1);
    expect(stats.patterns).toHaveLength(1);
    for (const pattern of stats.patterns) {
      expect(pattern.kind).toBe("pattern");
    }
  });

  it("sets kind to 'anti-pattern' for anti-patterns file entries", async () => {
    const antiContent = `# Anti-Patterns
Based on 2 runs. Success rate: 40%.
- **bare-except** catch: silent failures
`;
    mockFileContents(null, antiContent);
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(5);
    expect(stats.patterns).toHaveLength(1);
    for (const pattern of stats.patterns) {
      expect(pattern.kind).toBe("anti-pattern");
    }
  });

  it("includes description from bullet text with full capture", async () => {
    // The regex captures: **medium** as group 1 and everything after `: ` as group 2
    // For `- **medium** risk: 80% success rate`:
    //   group1 = "medium", group2 = "risk: 80% success rate"
    //   description = "medium: risk: 80% success rate"
    const patternsContent = `# Patterns
Based on 5 runs. Success rate: 80%.
- **medium** risk: 80% success rate
`;
    mockFileContents(patternsContent, null);
    mockStat.mockResolvedValue({ mtime: new Date() });

    const stats = await loadLearningStats(5);
    expect(stats.patterns[0].description).toBe("medium: risk: 80% success rate");
  });

  it("handles content with no bullet items", async () => {
    const patternsContent = `# Agent Patterns

Based on 1 runs. Success rate: 100%.

No specific patterns extracted yet.
`;
    mockFileContents(patternsContent, null);
    mockStat.mockResolvedValue({ mtime: new Date() });

    const stats = await loadLearningStats(1);
    expect(stats.patternsDiscovered).toBe(0);
    expect(stats.patterns).toEqual([]);
  });

  it("returns totalOutcomes matching the input parameter", async () => {
    mockReadFile.mockRejectedValue(new Error("ENOENT"));
    mockStat.mockRejectedValue(new Error("ENOENT"));

    const stats = await loadLearningStats(42);
    expect(stats.totalOutcomes).toBe(42);
  });
});
