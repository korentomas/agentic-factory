import { upsertRepository } from "@/lib/db/queries";

interface GitHubInstallation {
  id: number;
  app_id: number;
  app_slug: string;
}

interface GitHubRepo {
  id: number;
  full_name: string;
}

export interface SyncResult {
  synced: number;
  error?: string;
}

/**
 * Sync GitHub App installations and their repositories for the authenticated user.
 * Uses the user's OAuth access token to discover installations and repos,
 * then upserts them into the repositories table.
 */
export async function syncGitHubRepos(
  userId: string,
  accessToken: string,
): Promise<SyncResult> {
  if (!accessToken) {
    return { synced: 0, error: "no_token" };
  }

  const headers: Record<string, string> = {
    Authorization: `Bearer ${accessToken}`,
    Accept: "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
  };

  // List all app installations accessible to the user
  const instRes = await fetch("https://api.github.com/user/installations", {
    headers,
    cache: "no-store",
  });

  if (!instRes.ok) {
    const body = await instRes.text().catch(() => "");
    console.error(
      `[sync-repos] GET /user/installations failed: ${instRes.status} ${instRes.statusText}`,
      body.slice(0, 200),
    );
    return {
      synced: 0,
      error: `github_api_${instRes.status}`,
    };
  }

  const instData: { installations: GitHubInstallation[] } = await instRes.json();
  const installations = instData.installations ?? [];

  if (installations.length === 0) {
    return { synced: 0, error: "no_installations" };
  }

  let synced = 0;

  for (const inst of installations) {
    // Fetch repos for this installation
    const reposRes = await fetch(
      `https://api.github.com/user/installations/${inst.id}/repositories?per_page=100`,
      { headers, cache: "no-store" },
    );

    if (!reposRes.ok) {
      console.error(
        `[sync-repos] GET /user/installations/${inst.id}/repositories failed: ${reposRes.status}`,
      );
      continue;
    }

    const reposData: { repositories: GitHubRepo[] } = await reposRes.json();
    const repos = reposData.repositories ?? [];

    for (const repo of repos) {
      try {
        await upsertRepository({
          userId,
          githubRepoId: repo.id,
          fullName: repo.full_name,
          installationId: inst.id,
        });
        synced++;
      } catch (err) {
        console.error(
          `[sync-repos] upsertRepository failed for ${repo.full_name}:`,
          err,
        );
      }
    }
  }

  return { synced };
}
