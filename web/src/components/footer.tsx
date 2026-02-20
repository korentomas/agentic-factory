import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border bg-muted">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="grid grid-cols-1 gap-12 md:grid-cols-4">
          <div className="md:col-span-2">
            <p className="text-lg font-medium">LailaTov</p>
            <p className="mt-2 max-w-[40ch] text-sm text-muted-foreground">
              A codebase that never sleeps. Autonomous coding agents that turn
              issues into reviewed pull requests while you rest.
            </p>
          </div>

          <div>
            <p className="text-sm font-medium">Product</p>
            <ul className="mt-4 space-y-2">
              <li>
                <Link
                  href="#features"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Features
                </Link>
              </li>
              <li>
                <Link
                  href="#pricing"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Pricing
                </Link>
              </li>
              <li>
                <Link
                  href="#engines"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Engines
                </Link>
              </li>
            </ul>
          </div>

          <div>
            <p className="text-sm font-medium">Company</p>
            <ul className="mt-4 space-y-2">
              <li>
                <a
                  href="https://github.com/korentomas/agentic-factory"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  GitHub
                </a>
              </li>
              <li>
                <Link
                  href="/privacy"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Privacy
                </Link>
              </li>
              <li>
                <Link
                  href="/terms"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Terms
                </Link>
              </li>
            </ul>
          </div>
        </div>

        <div className="mt-12 border-t border-border pt-8">
          <p className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} LailaTov. A codebase that never sleeps.
          </p>
        </div>
      </div>
    </footer>
  );
}
