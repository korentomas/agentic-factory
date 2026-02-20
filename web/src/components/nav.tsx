import Link from "next/link";
import { MobileMenu } from "./mobile-menu";
import { ThemeToggle } from "./theme-toggle";

export function Nav() {
  return (
    <nav aria-label="Main navigation" className="fixed top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-sm">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link
          href="/"
          className="flex items-center gap-2 text-lg font-medium tracking-tight text-foreground"
        >
          <img
            src="/logo.png"
            alt=""
            className="h-6 w-6 dark:hidden"
            style={{ imageRendering: "pixelated" }}
          />
          <img
            src="/logo-dark.png"
            alt=""
            className="hidden h-6 w-6 dark:block"
            style={{ imageRendering: "pixelated" }}
          />
          LailaTov
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          <Link
            href="#features"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Features
          </Link>
          <Link
            href="#pricing"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Pricing
          </Link>
          <Link
            href="#engines"
            className="text-sm text-muted-foreground transition-colors hover:text-foreground"
          >
            Engines
          </Link>
          <ThemeToggle />
          <Link
            href="/chat"
            className="rounded-md bg-primary px-4 py-2 text-sm text-primary-foreground transition-colors hover:bg-primary/90"
          >
            Dashboard
          </Link>
        </div>
        <MobileMenu />
      </div>
    </nav>
  );
}
