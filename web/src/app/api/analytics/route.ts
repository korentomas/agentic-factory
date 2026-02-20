import { NextResponse } from "next/server";
import { auth } from "@/lib/auth";
import { loadDashboardData } from "@/lib/data";
import { getRepositories } from "@/lib/db/queries";

async function checkRunnerHealth(): Promise<boolean> {
  const runnerUrl = process.env.RUNNER_API_URL;
  if (!runnerUrl) return false;
  try {
    const res = await fetch(`${runnerUrl}/health`, {
      headers: { Authorization: `Bearer ${process.env.RUNNER_API_KEY || ""}` },
      signal: AbortSignal.timeout(5000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: "Unauthorized" }, { status: 401 });
  }

  const userId = session.user.id;
  const accessToken = session.accessToken;

  const [data, repos, runnerOk] = await Promise.all([
    loadDashboardData(accessToken),
    getRepositories(userId),
    checkRunnerHealth(),
  ]);

  return NextResponse.json({
    ...data,
    repoCount: repos.length,
    runnerOk,
    userName: session.user.name,
  });
}
