import { redirect } from "next/navigation";
import Link from "next/link";
import { auth, signOut } from "@/lib/auth";

export default async function Dashboard() {
  const session = await auth();

  if (!session?.user) {
    redirect("/login");
  }

  const user = session.user;

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      {/* Dashboard nav */}
      <nav className="border-b border-[var(--color-border)] bg-[var(--color-bg-surface)]">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-[var(--space-6)]">
          <Link
            href="/"
            className="text-[var(--text-lg)] font-medium tracking-tight text-[var(--color-text)]"
          >
            LailaTov
          </Link>

          <div className="flex items-center gap-[var(--space-4)]">
            <span className="text-[var(--text-sm)] text-[var(--color-text-secondary)]">
              {user.name || user.email}
            </span>
            {user.image && (
              <img
                src={user.image}
                alt=""
                className="h-8 w-8 rounded-full"
              />
            )}
            <form
              action={async () => {
                "use server";
                await signOut({ redirectTo: "/" });
              }}
            >
              <button
                type="submit"
                className="text-[var(--text-sm)] text-[var(--color-text-muted)] transition-colors hover:text-[var(--color-text)]"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-6xl px-[var(--space-6)] py-[var(--space-12)]">
        {/* Welcome */}
        <div className="mb-[var(--space-12)]">
          <h1 className="text-[var(--text-3xl)] font-semibold tracking-tight">
            Welcome back, {user.name?.split(" ")[0] || "developer"}
          </h1>
          <p className="mt-[var(--space-2)] text-[var(--color-text-secondary)]">
            Your autonomous code factory is ready.
          </p>
        </div>

        {/* Quick stats */}
        <div className="mb-[var(--space-12)] grid grid-cols-1 gap-[var(--space-4)] sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Tasks this month", value: "0", sub: "of 30" },
            { label: "PRs shipped", value: "0", sub: "all time" },
            { label: "Repositories", value: "0", sub: "connected" },
            { label: "Success rate", value: "--", sub: "no data yet" },
          ].map(({ label, value, sub }) => (
            <div
              key={label}
              className="rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-6)]"
            >
              <p className="text-[var(--text-sm)] text-[var(--color-text-muted)]">
                {label}
              </p>
              <p className="mt-[var(--space-2)] text-[var(--text-3xl)] font-semibold tracking-tight">
                {value}
              </p>
              <p className="mt-[var(--space-1)] text-[var(--text-xs)] text-[var(--color-text-muted)]">
                {sub}
              </p>
            </div>
          ))}
        </div>

        {/* Connect repo CTA */}
        <section className="mb-[var(--space-12)] rounded-[var(--radius-lg)] border border-[var(--color-border)] bg-[var(--color-bg-surface)] p-[var(--space-8)]">
          <h2 className="text-[var(--text-xl)] font-medium">
            Connect your first repository
          </h2>
          <p className="mt-[var(--space-3)] max-w-[52ch] text-[var(--color-text-secondary)]">
            Install the LailaTov GitHub App on your repository to start
            turning issues into pull requests automatically.
          </p>
          <a
            href="https://github.com/apps/agentfactory-bot/installations/new"
            className="mt-[var(--space-6)] inline-block rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-6)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
          >
            Install GitHub App
          </a>
        </section>

        {/* Recent activity (empty state) */}
        <section>
          <h2 className="text-[var(--text-xl)] font-medium">
            Recent activity
          </h2>
          <div className="mt-[var(--space-6)] rounded-[var(--radius-lg)] border border-dashed border-[var(--color-border-strong)] p-[var(--space-12)] text-center">
            <p className="text-[var(--color-text-muted)]">
              No tasks yet. Label a GitHub issue with{" "}
              <code className="rounded bg-[var(--color-bg-secondary)] px-[var(--space-2)] py-[var(--space-1)] font-mono text-[var(--text-sm)]">
                ai-agent
              </code>{" "}
              to get started.
            </p>
          </div>
        </section>
      </main>
    </div>
  );
}
