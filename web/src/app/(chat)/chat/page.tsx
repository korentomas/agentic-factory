import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { getRepositories } from "@/lib/db/queries";
import { syncGitHubRepos } from "@/lib/github/sync-repos";
import { DefaultView } from "@/components/v2/default-view";

export default async function ChatPage() {
  const session = await auth();

  if (!session?.user?.id) {
    redirect("/api/auth/signin");
  }

  // Sync repos from GitHub App installations before querying
  try {
    await syncGitHubRepos(session.user.id, session.accessToken);
  } catch (err) {
    console.error("[chat] syncGitHubRepos threw:", err);
  }

  const repos = await getRepositories(session.user.id);
  const hasRepos = repos.length > 0;

  return (
    <div className="bg-background h-screen">
      <DefaultView hasRepos={hasRepos} />
    </div>
  );
}
