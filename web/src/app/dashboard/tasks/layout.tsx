import Link from "next/link";
import { redirect } from "next/navigation";
import Image from "next/image";
import { auth, signOut } from "@/lib/auth";
import { ThemeToggle } from "@/components/theme-toggle";

export default async function TasksLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await auth();
  if (!session?.user) redirect("/login");
  const user = session.user;

  return (
    <div className="min-h-screen bg-[var(--color-bg)]">
      <nav
        aria-label="Tasks navigation"
        className="border-b border-[var(--color-border)] bg-[var(--color-bg-surface)]"
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-[var(--space-6)]">
          <div className="flex items-center gap-[var(--space-6)]">
            <Link
              href="/"
              className="text-[var(--text-lg)] font-medium tracking-tight text-[var(--color-text)]"
            >
              LailaTov
            </Link>
            <div className="flex gap-[var(--space-1)]">
              <Link
                href="/dashboard"
                className="rounded-[var(--radius-md)] px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] text-[var(--color-text-muted)] hover:bg-[var(--color-bg-secondary)] hover:text-[var(--color-text)]"
              >
                Dashboard
              </Link>
              <Link
                href="/dashboard/tasks"
                className="rounded-[var(--radius-md)] bg-[var(--color-bg-secondary)] px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)] font-medium text-[var(--color-text)]"
              >
                Tasks
              </Link>
            </div>
          </div>

          <div className="flex items-center gap-[var(--space-4)]">
            <ThemeToggle />
            <span className="text-[var(--text-sm)] text-[var(--color-text-secondary)]">
              {user.name || user.email}
            </span>
            {user.image && (
              <Image
                src={user.image}
                alt={`${user.name || "User"} avatar`}
                width={32}
                height={32}
                className="rounded-full"
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

      <main className="mx-auto max-w-7xl px-[var(--space-6)] py-[var(--space-8)]">
        {children}
      </main>
    </div>
  );
}
