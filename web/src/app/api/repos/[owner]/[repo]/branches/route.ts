import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";

interface GitHubBranch {
  name: string;
  protected: boolean;
}

interface GitHubRepoMeta {
  default_branch: string;
}

export async function GET(
  _req: Request,
  { params }: { params: Promise<{ owner: string; repo: string }> },
) {
  const session = await auth();
  if (!session?.user?.id || !session.accessToken) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const { owner, repo } = await params;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${session.accessToken}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  // Fetch repo metadata (for default_branch) and branches list in parallel
  const [metaRes, branchesRes] = await Promise.all([
    fetch(`https://api.github.com/repos/${owner}/${repo}`, {
      headers,
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    }),
    fetch(
      `https://api.github.com/repos/${owner}/${repo}/branches?per_page=100`,
      {
        headers,
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      },
    ),
  ]);

  if (!metaRes.ok || !branchesRes.ok) {
    const status = !metaRes.ok ? metaRes.status : branchesRes.status;
    return NextResponse.json(
      { error: `GitHub API error (${status})` },
      { status },
    );
  }

  const meta: GitHubRepoMeta = await metaRes.json();
  const branches: GitHubBranch[] = await branchesRes.json();

  // Sort: default branch first, then alphabetical
  const defaultBranch = meta.default_branch;
  const sorted = branches.sort((a, b) => {
    if (a.name === defaultBranch) return -1;
    if (b.name === defaultBranch) return 1;
    return a.name.localeCompare(b.name);
  });

  return NextResponse.json({
    defaultBranch,
    branches: sorted.map((b) => ({
      name: b.name,
      protected: b.protected,
      isDefault: b.name === defaultBranch,
    })),
  });
}
