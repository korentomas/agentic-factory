import { after } from "next/server";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { getRepositories, getTaskThreads } from "@/lib/db/queries";
import { syncGitHubReposDebounced } from "@/lib/github/sync-repos";
import { DefaultView } from "@/components/v2/default-view";
import { SWRFallbackProvider } from "@/components/v2/swr-fallback-provider";

export default async function ChatPage() {
  const session = await auth();

  if (!session?.user?.id) {
    redirect("/api/auth/signin");
  }

  // Extract after the guard so TS narrows into closures
  const userId = session.user.id;
  const accessToken = session.accessToken;

  // Fire-and-forget: sync runs AFTER HTML is sent to the client
  after(async () => {
    try {
      await syncGitHubReposDebounced(userId, accessToken);
    } catch (err) {
      console.error("[chat] syncGitHubRepos threw:", err);
    }
  });

  const [repos, threads] = await Promise.all([
    getRepositories(userId),
    getTaskThreads(userId),
  ]);
  const hasRepos = repos.length > 0;

  // Serialize thread dates to match the JSON shape returned by GET /api/tasks
  const serializedThreads = threads.map((t) => ({
    ...t,
    createdAt:
      t.createdAt instanceof Date ? t.createdAt.toISOString() : t.createdAt,
    updatedAt:
      t.updatedAt instanceof Date ? t.updatedAt.toISOString() : t.updatedAt,
  }));

  return (
    <div className="bg-background h-screen">
      <SWRFallbackProvider
        fallback={{ "/api/tasks": { threads: serializedThreads } }}
      >
        <DefaultView hasRepos={hasRepos} />
      </SWRFallbackProvider>
    </div>
  );
}
