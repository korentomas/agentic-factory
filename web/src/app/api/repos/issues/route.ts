import { NextRequest, NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { getRepositories } from "@/lib/db/queries";

interface GitHubIssue {
  number: number;
  title: string;
  html_url: string;
  labels: Array<{ name: string; color: string }>;
  created_at: string;
  pull_request?: unknown;
}

export interface IssueItem {
  title: string;
  number: number;
  repoFullName: string;
  url: string;
  labels: Array<{ name: string; color: string }>;
}

export async function GET(req: NextRequest) {
  const session = await auth();
  if (!session?.user?.id || !session.accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const searchParams = req.nextUrl.searchParams;
  const repoFilter = searchParams.get("repo");

  const repos = await getRepositories(session.user.id);
  if (repos.length === 0) {
    return NextResponse.json({ issues: [] });
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.accessToken}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  // Filter repos if a specific repo was requested
  const targetRepos = repoFilter
    ? repos.filter((r) => r.fullName === repoFilter)
    : repos;

  // Fetch issues from each repo in parallel (max 3 per repo, up to 5 repos)
  const reposToQuery = targetRepos.slice(0, 5);
  const issuePromises = reposToQuery.map(async (repo): Promise<IssueItem[]> => {
    try {
      const res = await fetch(
        `https://api.github.com/repos/${repo.fullName}/issues?state=open&per_page=3&sort=updated&direction=desc`,
        {
          headers,
          signal: AbortSignal.timeout(8000),
          cache: "no-store",
        },
      );

      if (!res.ok) return [];

      const issues: GitHubIssue[] = await res.json();

      // Filter out pull requests (GitHub API returns PRs as issues too)
      return issues
        .filter((issue) => !issue.pull_request)
        .map((issue) => ({
          title: issue.title,
          number: issue.number,
          repoFullName: repo.fullName,
          url: issue.html_url,
          labels: issue.labels.map((l) => ({ name: l.name, color: l.color })),
        }));
    } catch {
      return [];
    }
  });

  const results = await Promise.all(issuePromises);
  const allIssues = results
    .flat()
    .sort((a, b) => {
      // If filtering by repo, keep the order; otherwise interleave across repos
      if (repoFilter) return 0;
      return a.repoFullName.localeCompare(b.repoFullName);
    })
    .slice(0, 6);

  return NextResponse.json({ issues: allIssues });
}
