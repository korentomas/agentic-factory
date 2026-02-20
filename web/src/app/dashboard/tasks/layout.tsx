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
    <div className="min-h-screen bg-background">
      <nav
        aria-label="Tasks navigation"
        className="border-b border-border bg-card"
      >
        <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
          <div className="flex items-center gap-6">
            <Link
              href="/"
              className="text-lg font-medium tracking-tight text-foreground"
            >
              LailaTov
            </Link>
            <div className="flex gap-1">
              <Link
                href="/dashboard"
                className="rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                Dashboard
              </Link>
              <Link
                href="/dashboard/tasks"
                className="rounded-md bg-muted px-3 py-2 text-sm font-medium text-foreground"
              >
                Tasks
              </Link>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <ThemeToggle />
            <span className="text-sm text-muted-foreground">
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
                className="text-sm text-muted-foreground transition-colors hover:text-foreground"
              >
                Sign out
              </button>
            </form>
          </div>
        </div>
      </nav>

      <main className="mx-auto max-w-7xl px-6 py-8">
        {children}
      </main>
    </div>
  );
}
