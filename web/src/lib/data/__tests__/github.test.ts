import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import type { AgentOutcome, PRDetail } from "../types";
import { fetchPRDetails, fetchCodeRetention } from "../github";

/** Helper to create a realistic AgentOutcome for testing. */
function makeOutcome(overrides: Partial<AgentOutcome> = {}): AgentOutcome {
  return {
    outcome: "clean",
    pr_url: "https://github.com/korentomas/agentic-factory/pull/1",
    pr_number: 1,
    branch: "agent/task-1",
    risk_tier: "medium",
    checks: {
      gate: "success",
      tests: "success",
      review: "success",
      spec_audit: "success",
    },
    files_changed: ["src/main.py"],
    review_findings: [],
    run_id: "run-001",
    timestamp: "2026-02-10T12:00:00Z",
    model: "claude-sonnet-4-6",
    cost_usd: 0.05,
    duration_ms: 120000,
    engine: "claude-code",
    num_turns: 3,
    ...overrides,
  };
}

/** Helper to create a mock GitHub PR API response. */
function makeGitHubPR(overrides: Record<string, unknown> = {}) {
  return {
    number: 1,
    html_url: "https://github.com/korentomas/agentic-factory/pull/1",
    title: "feat: add new feature",
    state: "closed",
    merged_at: "2026-02-10T14:00:00Z",
    head: { ref: "agent/task-1" },
    created_at: "2026-02-10T12:00:00Z",
    additions: 50,
    deletions: 10,
    changed_files: 3,
    ...overrides,
  };
}

/** Helper to create a PRDetail for testing fetchCodeRetention. */
function makePRDetail(overrides: Partial<PRDetail> = {}): PRDetail {
  return {
    number: 1,
    url: "https://github.com/korentomas/agentic-factory/pull/1",
    title: "feat: add new feature",
    state: "merged",
    branch: "agent/task-1",
    outcome: "clean",
    riskTier: "medium",
    engine: "claude-code",
    model: "claude-sonnet-4-6",
    cost: 0.05,
    duration: 120000,
    numTurns: 3,
    filesChanged: ["src/main.py"],
    checksStatus: {
      gate: "success",
      tests: "success",
      review: "success",
      spec_audit: "success",
    },
    timestamp: "2026-02-10T12:00:00Z",
    mergedAt: "2026-02-10T14:00:00Z",
    ...overrides,
  };
}

describe("fetchPRDetails", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("fetches and enriches PR data from GitHub API", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeGitHubPR()),
    });

    const outcomes = [makeOutcome({ pr_number: 1 })];
    const prs = await fetchPRDetails(outcomes);

    expect(prs).toHaveLength(1);
    expect(prs[0].title).toBe("feat: add new feature");
    expect(prs[0].state).toBe("merged");
    expect(prs[0].mergedAt).toBe("2026-02-10T14:00:00Z");
  });

  it("falls back to outcome data when API returns non-ok", async () => {
    fetchMock.mockResolvedValue({
      ok: false,
      status: 403,
    });

    const outcomes = [makeOutcome({ pr_number: 42, branch: "agent/task-42" })];
    const prs = await fetchPRDetails(outcomes);

    expect(prs).toHaveLength(1);
    expect(prs[0].title).toBe("PR #42 (agent/task-42)");
    expect(prs[0].mergedAt).toBeNull();
  });

  it("falls back to outcome data when fetch throws", async () => {
    fetchMock.mockRejectedValue(new Error("Network error"));

    const outcomes = [makeOutcome({ pr_number: 10 })];
    const prs = await fetchPRDetails(outcomes);

    expect(prs).toHaveLength(1);
    expect(prs[0].number).toBe(10);
    expect(prs[0].title).toBe("PR #10 (agent/task-1)");
  });

  it("deduplicates outcomes by PR number", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeGitHubPR({ number: 5 })),
    });

    const outcomes = [
      makeOutcome({ pr_number: 5, timestamp: "2026-02-10T12:00:00Z" }),
      makeOutcome({ pr_number: 5, timestamp: "2026-02-10T13:00:00Z" }),
      makeOutcome({ pr_number: 5, timestamp: "2026-02-10T14:00:00Z" }),
    ];
    const prs = await fetchPRDetails(outcomes);

    expect(prs).toHaveLength(1);
    // Should use the latest outcome (last in the array)
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("sorts results by timestamp descending", async () => {
    fetchMock.mockImplementation((url: string) => {
      const prNum = parseInt(url.split("/").pop()!);
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(makeGitHubPR({ number: prNum })),
      });
    });

    const outcomes = [
      makeOutcome({ pr_number: 1, timestamp: "2026-02-08T12:00:00Z" }),
      makeOutcome({ pr_number: 2, timestamp: "2026-02-10T12:00:00Z" }),
      makeOutcome({ pr_number: 3, timestamp: "2026-02-09T12:00:00Z" }),
    ];
    const prs = await fetchPRDetails(outcomes);

    expect(prs[0].number).toBe(2);
    expect(prs[1].number).toBe(3);
    expect(prs[2].number).toBe(1);
  });

  it("sends authorization header when access token is provided", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeGitHubPR()),
    });

    await fetchPRDetails([makeOutcome()], "ghp_test_token");

    const callArgs = fetchMock.mock.calls[0];
    expect(callArgs[1].headers.Authorization).toBe("Bearer ghp_test_token");
  });

  it("does not send authorization header when no token", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(makeGitHubPR()),
    });

    await fetchPRDetails([makeOutcome()]);

    const callArgs = fetchMock.mock.calls[0];
    expect(callArgs[1].headers.Authorization).toBeUndefined();
  });

  it("maps merged_at to state 'merged'", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve(
          makeGitHubPR({ merged_at: "2026-02-10T14:00:00Z", state: "closed" })
        ),
    });

    const prs = await fetchPRDetails([makeOutcome()]);
    expect(prs[0].state).toBe("merged");
  });

  it("maps null merged_at to actual state", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve(makeGitHubPR({ merged_at: null, state: "open" })),
    });

    const prs = await fetchPRDetails([makeOutcome()]);
    expect(prs[0].state).toBe("open");
  });

  it("defaults engine and model in fallback path", async () => {
    fetchMock.mockRejectedValue(new Error("fail"));

    const outcomes = [
      makeOutcome({ engine: undefined, model: undefined }),
    ];
    const prs = await fetchPRDetails(outcomes);

    expect(prs[0].engine).toBe("claude-code");
    expect(prs[0].model).toBe("claude-sonnet-4-6");
  });

  it("defaults cost, duration, numTurns to 0 when missing", async () => {
    fetchMock.mockRejectedValue(new Error("fail"));

    const outcomes = [
      makeOutcome({ cost_usd: undefined, duration_ms: undefined, num_turns: undefined }),
    ];
    const prs = await fetchPRDetails(outcomes);

    expect(prs[0].cost).toBe(0);
    expect(prs[0].duration).toBe(0);
    expect(prs[0].numTurns).toBe(0);
  });

  it("returns empty array for no outcomes", async () => {
    const prs = await fetchPRDetails([]);
    expect(prs).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("fetchCodeRetention", () => {
  let fetchMock: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("computes retention for a merged PR where bot is latest author", async () => {
    // First call: PR files
    // Second call: blame/commits for the file
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { filename: "src/main.py", status: "modified", additions: 30, deletions: 5 },
          ]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { author: { login: "agentfactory-bot[bot]" }, sha: "abc123" },
          ]),
      });

    const prs = [makePRDetail({ filesChanged: ["abc123"] })];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toHaveLength(1);
    expect(retention[0].linesWritten).toBe(30);
    expect(retention[0].retentionRate).toBeGreaterThan(0);
  });

  it("skips non-merged PRs", async () => {
    const prs = [makePRDetail({ mergedAt: null })];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("detects human overwrite when non-bot is latest author", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { filename: "src/main.py", status: "modified", additions: 20, deletions: 3 },
          ]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { author: { login: "human-dev" }, sha: "def456" },
            { author: { login: "agentfactory-bot[bot]" }, sha: "abc123" },
          ]),
      });

    const prs = [makePRDetail()];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toHaveLength(1);
    expect(retention[0].overwrittenByHuman).toBe(20);
    expect(retention[0].linesOverwritten).toBe(20);
  });

  it("handles blame API failure gracefully (adds to retained)", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { filename: "src/main.py", status: "modified", additions: 15, deletions: 2 },
          ]),
      })
      .mockRejectedValueOnce(new Error("API error"));

    const prs = [makePRDetail()];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toHaveLength(1);
    expect(retention[0].linesRetained).toBe(15);
  });

  it("handles files API failure gracefully (skips PR)", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: false,
      status: 404,
    });

    const prs = [makePRDetail()];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toEqual([]);
  });

  it("limits to 10 most recent merged PRs", async () => {
    const prs = Array.from({ length: 15 }, (_, i) =>
      makePRDetail({ number: i + 1, mergedAt: `2026-02-${String(i + 1).padStart(2, "0")}T12:00:00Z` })
    );

    // Mock responses for each of the 10 PRs that will be processed
    for (let i = 0; i < 10; i++) {
      fetchMock
        .mockResolvedValueOnce({
          ok: true,
          json: () => Promise.resolve([]),
        });
    }

    const retention = await fetchCodeRetention(prs);

    // Should only make 10 fetch calls (one per PR, for files)
    expect(fetchMock).toHaveBeenCalledTimes(10);
  });

  it("sends authorization header when token provided", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () => Promise.resolve([]),
    });

    const prs = [makePRDetail()];
    await fetchCodeRetention(prs, "ghp_test_token");

    const callArgs = fetchMock.mock.calls[0];
    expect(callArgs[1].headers.Authorization).toBe("Bearer ghp_test_token");
  });

  it("computes retention rate correctly", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { filename: "a.py", status: "modified", additions: 40, deletions: 0 },
            { filename: "b.py", status: "modified", additions: 60, deletions: 0 },
          ]),
      })
      // blame for a.py — bot is latest (retained)
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { author: { login: "agentfactory-bot[bot]" }, sha: "abc" },
          ]),
      })
      // blame for b.py — human is latest (overwritten)
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { author: { login: "human-dev" }, sha: "def" },
            { author: { login: "agentfactory-bot[bot]" }, sha: "ghi" },
          ]),
      });

    const prs = [makePRDetail({ filesChanged: ["abc"] })];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toHaveLength(1);
    expect(retention[0].linesWritten).toBe(100);
    // a.py: 40 retained (bot is latest and sha matches filesChanged[0])
    // b.py: 60 overwritten by human
    expect(retention[0].retentionRate).toBeCloseTo(0.4, 1);
  });

  it("handles fetch throwing for entire PR", async () => {
    fetchMock.mockRejectedValueOnce(new Error("Network failure"));

    const prs = [makePRDetail()];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toEqual([]);
  });

  it("returns file list from GitHub files API", async () => {
    fetchMock.mockResolvedValueOnce({
      ok: true,
      json: () =>
        Promise.resolve([
          { filename: "src/app.py", status: "modified", additions: 10, deletions: 2 },
          { filename: "tests/test_app.py", status: "added", additions: 25, deletions: 0 },
        ]),
    })
    // blame for src/app.py
    .mockResolvedValueOnce({
      ok: false,
      status: 403,
    })
    // blame for tests/test_app.py
    .mockResolvedValueOnce({
      ok: false,
      status: 403,
    });

    const prs = [makePRDetail()];
    const retention = await fetchCodeRetention(prs);

    expect(retention[0].filesChanged).toEqual(["src/app.py", "tests/test_app.py"]);
  });

  it("returns empty array when given empty PR list", async () => {
    const retention = await fetchCodeRetention([]);
    expect(retention).toEqual([]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("handles agent overwriting agent code (different PR)", async () => {
    fetchMock
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { filename: "src/main.py", status: "modified", additions: 25, deletions: 5 },
          ]),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: () =>
          Promise.resolve([
            { author: { login: "agentfactory-bot[bot]" }, sha: "different-sha" },
          ]),
      });

    // filesChanged[0] is "src/main.py" but the latest commit sha is "different-sha"
    const prs = [makePRDetail({ filesChanged: ["src/main.py"] })];
    const retention = await fetchCodeRetention(prs);

    expect(retention).toHaveLength(1);
    // The agent is latest author but sha doesn't match filesChanged[0] => overwrittenByAgent
    expect(retention[0].overwrittenByAgent).toBe(25);
  });
});
