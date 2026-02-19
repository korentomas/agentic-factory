"use client";

import { useState } from "react";
import Link from "next/link";
import { Menu, X } from "lucide-react";
import { ThemeToggle } from "./theme-toggle";

export function MobileMenu() {
  const [open, setOpen] = useState(false);

  return (
    <div className="md:hidden">
      <button
        onClick={() => setOpen(true)}
        aria-label="Open menu"
        className="p-[var(--space-2)] text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text)]"
      >
        <Menu className="h-5 w-5" />
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />

          <div className="fixed inset-y-0 right-0 z-50 w-64 bg-[var(--color-bg-surface)] shadow-[var(--shadow-lg)]">
            <div className="flex h-16 items-center justify-end px-[var(--space-6)]">
              <button
                onClick={() => setOpen(false)}
                aria-label="Close menu"
                className="p-[var(--space-2)] text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text)]"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <nav className="flex flex-col gap-[var(--space-2)] px-[var(--space-6)]">
              <Link
                href="#features"
                onClick={() => setOpen(false)}
                className="rounded-[var(--radius-md)] px-[var(--space-3)] py-[var(--space-3)] text-[var(--text-sm)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
              >
                Features
              </Link>
              <Link
                href="#pricing"
                onClick={() => setOpen(false)}
                className="rounded-[var(--radius-md)] px-[var(--space-3)] py-[var(--space-3)] text-[var(--text-sm)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
              >
                Pricing
              </Link>
              <Link
                href="#engines"
                onClick={() => setOpen(false)}
                className="rounded-[var(--radius-md)] px-[var(--space-3)] py-[var(--space-3)] text-[var(--text-sm)] text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-bg-hover)] hover:text-[var(--color-text)]"
              >
                Engines
              </Link>
              <div className="mt-[var(--space-2)] flex items-center gap-[var(--space-3)] px-[var(--space-3)]">
                <ThemeToggle />
                <span className="text-[var(--text-sm)] text-[var(--color-text-muted)]">Theme</span>
              </div>
              <Link
                href="/dashboard"
                onClick={() => setOpen(false)}
                className="mt-[var(--space-2)] rounded-[var(--radius-md)] bg-[var(--color-accent)] px-[var(--space-3)] py-[var(--space-3)] text-center text-[var(--text-sm)] text-[var(--color-text-inverse)] transition-colors hover:bg-[var(--color-accent-hover)]"
              >
                Dashboard
              </Link>
            </nav>
          </div>
        </>
      )}
    </div>
  );
}
