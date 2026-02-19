import type { AgentOutcome, CodeRetention, PRDetail } from "./types";

const GITHUB_API = "https://api.github.com";
const REPO = "korentomas/agentic-factory";
const BOT_LOGIN = "agentfactory-bot[bot]";

interface GitHubPR {
  number: number;
  html_url: string;
  title: string;
  state: string;
  merged_at: string | null;
  head: { ref: string };
  created_at: string;
  additions: number;
  deletions: number;
  changed_files: number;
}

interface GitHubFile {
  filename: string;
  status: string;
  additions: number;
  deletions: number;
  patch?: string;
}

interface BlameLine {
  author: string;
  commit: string;
}

/** Fetch PR details from GitHub, enriched with outcome data. */
export async function fetchPRDetails(
  outcomes: AgentOutcome[],
  accessToken?: string
): Promise<PRDetail[]> {
  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const prs: PRDetail[] = [];

  // Deduplicate by PR number (some PRs have multiple outcomes from remediation)
  const prNumbers = [...new Set(outcomes.map((o) => o.pr_number))];

  for (const prNum of prNumbers) {
    // Find the latest outcome for this PR
    const prOutcomes = outcomes.filter((o) => o.pr_number === prNum);
    const latestOutcome = prOutcomes[prOutcomes.length - 1];

    try {
      const res = await fetch(`${GITHUB_API}/repos/${REPO}/pulls/${prNum}`, {
        headers,
        next: { revalidate: 300 }, // cache 5 min
      });

      if (!res.ok) {
        // Fallback: use outcome data only
        prs.push(prFromOutcome(latestOutcome));
        continue;
      }

      const ghPr = (await res.json()) as GitHubPR;

      prs.push({
        number: ghPr.number,
        url: ghPr.html_url,
        title: ghPr.title,
        state: ghPr.merged_at ? "merged" : (ghPr.state as "open" | "closed"),
        branch: ghPr.head.ref,
        outcome: latestOutcome.outcome,
        riskTier: latestOutcome.risk_tier,
        engine: latestOutcome.engine || "claude-code",
        model: latestOutcome.model || "claude-sonnet-4-6",
        cost: latestOutcome.cost_usd ?? 0,
        duration: latestOutcome.duration_ms ?? 0,
        numTurns: latestOutcome.num_turns ?? 0,
        filesChanged: latestOutcome.files_changed,
        checksStatus: latestOutcome.checks,
        timestamp: latestOutcome.timestamp,
        mergedAt: ghPr.merged_at,
      });
    } catch {
      prs.push(prFromOutcome(latestOutcome));
    }
  }

  return prs.sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );
}

/** Create a PRDetail from outcome data when GitHub API is unavailable. */
function prFromOutcome(o: AgentOutcome): PRDetail {
  return {
    number: o.pr_number,
    url: o.pr_url,
    title: `PR #${o.pr_number} (${o.branch})`,
    state: o.outcome === "clean" ? "merged" : "open",
    branch: o.branch,
    outcome: o.outcome,
    riskTier: o.risk_tier,
    engine: o.engine || "claude-code",
    model: o.model || "claude-sonnet-4-6",
    cost: o.cost_usd ?? 0,
    duration: o.duration_ms ?? 0,
    numTurns: o.num_turns ?? 0,
    filesChanged: o.files_changed,
    checksStatus: o.checks,
    timestamp: o.timestamp,
    mergedAt: null,
  };
}

/** Compute code retention metrics for merged PRs.
 *  Uses git blame to see how much agent-written code survives. */
export async function fetchCodeRetention(
  prs: PRDetail[],
  accessToken?: string
): Promise<CodeRetention[]> {
  const headers: Record<string, string> = {
    Accept: "application/vnd.github+json",
  };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const retention: CodeRetention[] = [];
  const mergedPrs = prs.filter((pr) => pr.mergedAt);

  for (const pr of mergedPrs.slice(0, 10)) {
    // limit to recent 10
    try {
      // Get files changed in the PR
      const filesRes = await fetch(
        `${GITHUB_API}/repos/${REPO}/pulls/${pr.number}/files`,
        { headers, next: { revalidate: 600 } }
      );

      if (!filesRes.ok) continue;

      const files = (await filesRes.json()) as GitHubFile[];
      let totalAdditions = 0;
      let retainedLines = 0;
      let overwrittenByAgent = 0;
      let overwrittenByHuman = 0;

      for (const file of files) {
        totalAdditions += file.additions;

        // Check blame for each file to see who last touched the lines
        try {
          const blameRes = await fetch(
            `${GITHUB_API}/repos/${REPO}/commits?path=${encodeURIComponent(file.filename)}&per_page=5`,
            { headers, next: { revalidate: 600 } }
          );

          if (!blameRes.ok) {
            retainedLines += file.additions;
            continue;
          }

          const commits = (await blameRes.json()) as Array<{
            author: { login: string } | null;
            sha: string;
          }>;

          // If the most recent commit to this file is by our bot, lines are retained
          const latestAuthor = commits[0]?.author?.login || "";
          if (
            latestAuthor === BOT_LOGIN ||
            latestAuthor.includes("agentfactory")
          ) {
            // Lines were last touched by an agent
            const isOurPr = commits[0]?.sha === pr.filesChanged[0]; // approximation
            if (isOurPr) {
              retainedLines += file.additions;
            } else {
              overwrittenByAgent += file.additions;
            }
          } else if (latestAuthor && commits.length > 0) {
            // Check if the original agent commit is still the latest
            const agentCommit = commits.find(
              (c) =>
                c.author?.login === BOT_LOGIN ||
                c.author?.login?.includes("agentfactory")
            );
            if (agentCommit && commits[0]?.sha === agentCommit.sha) {
              retainedLines += file.additions;
            } else if (agentCommit) {
              overwrittenByHuman += file.additions;
            } else {
              retainedLines += file.additions;
            }
          } else {
            retainedLines += file.additions;
          }
        } catch {
          retainedLines += file.additions;
        }
      }

      const total = totalAdditions || 1;
      retention.push({
        prNumber: pr.number,
        prUrl: pr.url,
        filesChanged: files.map((f) => f.filename),
        linesWritten: totalAdditions,
        linesRetained: retainedLines,
        linesOverwritten: overwrittenByAgent + overwrittenByHuman,
        overwrittenByAgent,
        overwrittenByHuman,
        retentionRate: retainedLines / total,
      });
    } catch {
      continue;
    }
  }

  return retention;
}
