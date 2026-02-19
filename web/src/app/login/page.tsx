import type { Metadata } from "next";
import Link from "next/link";
import { signIn } from "@/lib/auth";

export const metadata: Metadata = {
  title: "Sign in",
};

export default function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center">
      <div className="w-full max-w-sm rounded-[var(--radius-xl)] bg-[var(--color-bg-surface)] p-[var(--space-12)] shadow-[var(--shadow-md)]">
        <h1 className="text-center text-[var(--text-2xl)] font-semibold tracking-tight">
          Welcome to LailaTov
        </h1>
        <p className="mt-[var(--space-3)] text-center text-[var(--text-sm)] text-[var(--color-text-secondary)]">
          Sign in with GitHub to connect your repositories.
        </p>

        <form
          className="mt-[var(--space-8)]"
          action={async () => {
            "use server";
            await signIn("github", { redirectTo: "/dashboard" });
          }}
        >
          <button
            type="submit"
            className="flex w-full items-center justify-center gap-[var(--space-3)] rounded-[var(--radius-md)] bg-[var(--color-text)] px-[var(--space-4)] py-[var(--space-3)] text-[var(--text-sm)] font-medium text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-text-secondary)]"
          >
            <svg
              className="h-5 w-5"
              fill="currentColor"
              viewBox="0 0 20 20"
              aria-hidden="true"
            >
              <path
                fillRule="evenodd"
                d="M10 0C4.477 0 0 4.484 0 10.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0110 4.844c.85.004 1.705.115 2.504.337 1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.203 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.942.359.31.678.921.678 1.856 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0020 10.017C20 4.484 15.522 0 10 0z"
                clipRule="evenodd"
              />
            </svg>
            Continue with GitHub
          </button>
        </form>

        <p className="mt-[var(--space-6)] text-center text-[var(--text-xs)] text-[var(--color-text-muted)]">
          By signing in, you agree to our{" "}
          <Link
            href="/terms"
            className="underline hover:text-[var(--color-text-secondary)]"
          >
            Terms of Service
          </Link>{" "}
          and{" "}
          <Link
            href="/privacy"
            className="underline hover:text-[var(--color-text-secondary)]"
          >
            Privacy Policy
          </Link>
          .
        </p>
      </div>
    </div>
  );
}
