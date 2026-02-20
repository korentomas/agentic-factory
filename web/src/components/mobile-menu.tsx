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
        className="p-2 text-muted-foreground transition-colors hover:text-foreground"
      >
        <Menu className="h-5 w-5" />
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />

          <div className="fixed inset-y-0 right-0 z-50 w-64 bg-card shadow-lg">
            <div className="flex h-16 items-center justify-end px-6">
              <button
                onClick={() => setOpen(false)}
                aria-label="Close menu"
                className="p-2 text-muted-foreground transition-colors hover:text-foreground"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            <nav className="flex flex-col gap-2 px-6">
              <Link
                href="#features"
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                Features
              </Link>
              <Link
                href="#pricing"
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                Pricing
              </Link>
              <Link
                href="#engines"
                onClick={() => setOpen(false)}
                className="rounded-md px-3 py-3 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
              >
                Engines
              </Link>
              <div className="mt-2 flex items-center gap-3 px-3">
                <ThemeToggle />
                <span className="text-sm text-muted-foreground">Theme</span>
              </div>
              <Link
                href="/chat"
                onClick={() => setOpen(false)}
                className="mt-2 rounded-md bg-primary px-3 py-3 text-center text-sm text-primary-foreground transition-colors hover:bg-primary/90"
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
