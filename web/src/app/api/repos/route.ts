import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { getRepositories } from "@/lib/db/queries";

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const repos = await getRepositories(session.user.id);

  return NextResponse.json({
    repos: repos.map((r) => ({
      fullName: r.fullName,
      url: `https://github.com/${r.fullName}`,
      installationId: r.installationId,
    })),
  });
}
