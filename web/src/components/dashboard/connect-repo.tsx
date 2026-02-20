import Link from "next/link";
import { CheckCircle2, Circle, ExternalLink } from "lucide-react";

interface SetupStep {
  label: string;
  done: boolean;
  href?: string;
  description: string;
}

interface ConnectRepoProps {
  repoCount?: number;
  hasRunner?: boolean;
  syncError?: string;
}

function getSyncErrorMessage(syncError: string): string {
  switch (syncError) {
    case "no_token":
      return "GitHub token missing — try signing out and back in";
    case "no_installations":
      return "No GitHub App installation found — click Install above";
    case "sync_exception":
      return "Failed to sync repositories — try refreshing the page";
    default:
      if (syncError.startsWith("github_api_401")) {
        return "GitHub token expired — sign out and sign in again";
      }
      if (syncError.startsWith("github_api_")) {
        return `GitHub API error (${syncError.replace("github_api_", "")}) — try again later`;
      }
      return "Could not sync repositories — try refreshing";
  }
}

export function ConnectRepo({ repoCount = 0, hasRunner = false, syncError }: ConnectRepoProps) {
  const steps: SetupStep[] = [
    {
      label: "Sign in with GitHub",
      done: true, // Always true if they can see this component
      description: "Authenticated via GitHub OAuth",
    },
    {
      label: "Install the GitHub App",
      done: repoCount > 0,
      href: "https://github.com/apps/agentfactory-bot/installations/new",
      description:
        repoCount > 0
          ? `${repoCount} ${repoCount === 1 ? "repository" : "repositories"} connected`
          : syncError
            ? getSyncErrorMessage(syncError)
            : "Grant access to your repositories",
    },
    {
      label: "Runner connected",
      done: hasRunner,
      description: hasRunner
        ? "Agent runner is reachable"
        : "Cloud runner not configured yet",
    },
    {
      label: "Create your first task",
      done: false,
      description:
        "Describe a task in Chat, or open a GitHub issue — we pick it up automatically",
    },
  ];

  const completedCount = steps.filter((s) => s.done).length;
  const allPrereqsDone = steps[0].done && steps[1].done && steps[2].done;

  return (
    <section className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-8)]">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-[var(--text-xl)] font-medium">Get started</h2>
          <p className="mt-[var(--space-1)] text-[var(--text-sm)] text-[var(--color-text-secondary)]">
            {completedCount} of {steps.length} steps complete
          </p>
        </div>
        {/* Progress bar */}
        <div className="flex h-2 w-32 overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
          <div
            className="rounded-full bg-[var(--color-accent)] transition-all duration-300"
            style={{ width: `${(completedCount / steps.length) * 100}%` }}
          />
        </div>
      </div>

      <ol className="mt-[var(--space-6)] space-y-[var(--space-4)]">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-[var(--space-3)]">
            {step.done ? (
              <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-[var(--color-accent)]" />
            ) : (
              <Circle className="mt-0.5 h-5 w-5 shrink-0 text-[var(--color-text-muted)]" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-[var(--space-2)]">
                <span
                  className={`text-[var(--text-sm)] font-medium ${
                    step.done
                      ? "text-[var(--color-text)]"
                      : "text-[var(--color-text-muted)]"
                  }`}
                >
                  {step.label}
                </span>
                {step.href && !step.done && (
                  <a
                    href={step.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 rounded-[var(--radius-sm)] bg-[var(--color-accent)] px-[var(--space-2)] py-0.5 text-[var(--text-xs)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
                  >
                    Install
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
              <p className="text-[var(--text-xs)] text-[var(--color-text-muted)]">
                {step.description}
              </p>
            </div>
          </li>
        ))}
      </ol>

      {allPrereqsDone && (
        <Link
          href="/chat"
          className="mt-[var(--space-6)] inline-block rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-6)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
        >
          Create your first task
        </Link>
      )}
    </section>
  );
}
