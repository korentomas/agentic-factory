"use client";

import type { ReactNode } from "react";
import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import { useTheme } from "next-themes";
import { ArrowLeft, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserPopover } from "@/components/user-popover";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { label: "Tasks", href: "/chat" },
  { label: "Threads", href: "/chat/threads" },
  { label: "Analytics", href: "/analytics" },
  { label: "Settings", href: "/chat/settings" },
] as const;

interface AppHeaderProps {
  title?: string;
  showBackButton?: boolean;
  backHref?: string;
  showBrand?: boolean;
  titleContent?: ReactNode;
  className?: string;
  children?: ReactNode;
}

export function AppHeader({
  title,
  showBackButton,
  backHref = "/chat",
  showBrand,
  titleContent,
  className,
  children,
}: AppHeaderProps) {
  const router = useRouter();
  const pathname = usePathname();
  const { resolvedTheme } = useTheme();
  const logoSrc = resolvedTheme === "dark" ? "/logo-dark.png" : "/logo.png";
  const [mobileOpen, setMobileOpen] = useState(false);

  function isActive(href: string) {
    if (href === "/chat") {
      return pathname === "/chat";
    }
    return pathname.startsWith(href);
  }

  return (
    <div
      className={cn("border-border bg-card border-b px-4 py-2", className)}
    >
      <div className="flex items-center gap-3">
        {showBackButton && (
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:bg-muted hover:text-foreground h-8 w-8 p-0"
            onClick={() => router.push(backHref)}
          >
            <ArrowLeft className="h-4 w-4" />
          </Button>
        )}

        {showBrand && (
          <Link href="/chat" className="flex items-center gap-2">
            <Image
              src={logoSrc}
              alt="LailaTov"
              width={24}
              height={24}
              className="h-6 w-6"
              style={{ imageRendering: "pixelated" }}
              unoptimized
            />
            <span className="text-foreground text-base font-semibold tracking-tight">
              LailaTov
            </span>
          </Link>
        )}

        {title && !showBrand && (
          <h1 className="text-foreground text-lg font-semibold">{title}</h1>
        )}

        {/* Desktop nav */}
        {showBrand && (
          <nav className="hidden items-center gap-1 md:flex">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={cn(
                  "rounded-md px-3 py-1.5 text-sm transition-colors",
                  isActive(item.href)
                    ? "text-foreground font-medium"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted",
                )}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        )}

        {titleContent}

        <div className="ml-auto flex items-center gap-2">
          {children}
          <ThemeToggle />
          <UserPopover />

          {/* Mobile hamburger */}
          {showBrand && (
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 md:hidden"
                >
                  <Menu className="h-4 w-4" />
                </Button>
              </SheetTrigger>
              <SheetContent side="right" className="w-64">
                <SheetHeader>
                  <SheetTitle className="text-left">Navigation</SheetTitle>
                </SheetHeader>
                <nav className="mt-4 flex flex-col gap-1">
                  {NAV_ITEMS.map((item) => (
                    <Link
                      key={item.href}
                      href={item.href}
                      onClick={() => setMobileOpen(false)}
                      className={cn(
                        "rounded-md px-3 py-2 text-sm transition-colors",
                        isActive(item.href)
                          ? "bg-muted text-foreground font-medium"
                          : "text-muted-foreground hover:text-foreground hover:bg-muted",
                      )}
                    >
                      {item.label}
                    </Link>
                  ))}
                </nav>
              </SheetContent>
            </Sheet>
          )}
        </div>
      </div>
    </div>
  );
}
