import { after } from "next/server";
import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { syncGitHubReposDebounced } from "@/lib/github/sync-repos";
import { DefaultView } from "@/components/v2/default-view";

export default async function ChatPage() {
  const session = await auth();

  if (!session?.user?.id) {
    redirect("/api/auth/signin");
  }

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

  return (
    <div className="bg-background h-screen">
      <DefaultView />
    </div>
  );
}
