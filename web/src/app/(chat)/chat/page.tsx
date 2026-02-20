import { redirect } from "next/navigation";
import { auth } from "@/lib/auth";
import { getRepositories } from "@/lib/db/queries";
import { DefaultView } from "@/components/v2/default-view";

export default async function ChatPage() {
  const session = await auth();

  if (!session?.user?.id) {
    redirect("/api/auth/signin");
  }

  const repos = await getRepositories(session.user.id);
  const hasRepos = repos.length > 0;

  return (
    <div className="bg-background h-screen">
      <DefaultView hasRepos={hasRepos} />
    </div>
  );
}
