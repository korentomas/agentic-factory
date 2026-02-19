import { auth } from "@/lib/auth";

const REPO = "korentomas/agentic-factory";

interface BugReportBody {
  title: string;
  description: string;
  steps?: string;
  expected?: string;
  actual?: string;
  pageUrl?: string;
}

function renderBugReportBody(
  report: BugReportBody,
  user: { name?: string | null; email?: string | null }
): string {
  const sections = [
    "## Bug Report (User-submitted via LailaTov)",
    "",
    `**Reporter:** ${user.name || "Anonymous"} (${user.email || "no email"})`,
    "",
    "### Description",
    "",
    report.description,
  ];

  if (report.steps) {
    sections.push("", "### Steps to Reproduce", "", report.steps);
  }
  if (report.expected) {
    sections.push("", "### Expected Behavior", "", report.expected);
  }
  if (report.actual) {
    sections.push("", "### Actual Behavior", "", report.actual);
  }
  if (report.pageUrl) {
    sections.push("", "### Page URL", "", report.pageUrl);
  }

  sections.push("", "---", "*Submitted via the LailaTov bug report form.*");
  return sections.join("\n");
}

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.accessToken) {
    return Response.json({ error: "Not authenticated" }, { status: 401 });
  }

  const body: BugReportBody = await req.json();

  if (!body.title) {
    return Response.json({ error: "Title is required" }, { status: 400 });
  }

  const issueBody = renderBugReportBody(body, session.user ?? {});

  const response = await fetch(
    `https://api.github.com/repos/${REPO}/issues`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${session.accessToken}`,
        Accept: "application/vnd.github+json",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: `[user] ${body.title}`,
        body: issueBody,
        labels: ["bug", "user-reported", "ai-agent"],
      }),
    }
  );

  if (!response.ok) {
    const errorText = await response.text();
    return Response.json(
      { error: "Failed to create issue", detail: errorText },
      { status: response.status }
    );
  }

  const issue = await response.json();
  return Response.json({ issue_url: issue.html_url });
}
