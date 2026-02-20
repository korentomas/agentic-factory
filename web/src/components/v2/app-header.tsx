"use client";

import type { ReactNode } from "react";
import Image from "next/image";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { UserPopover } from "@/components/user-popover";
import { cn } from "@/lib/utils";

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
  const { resolvedTheme } = useTheme();
  const logoSrc = resolvedTheme === "dark" ? "/logo-dark.png" : "/logo.png";

  return (
    <div className={cn("border-border bg-card border-b px-4 py-2", className)}>
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
          <div className="flex items-center gap-2">
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
          </div>
        )}
        {title && !showBrand && (
          <h1 className="text-foreground text-lg font-semibold">{title}</h1>
        )}
        {titleContent}
        <div className="ml-auto flex items-center gap-2">
          {children}
          <ThemeToggle />
          <UserPopover />
        </div>
      </div>
    </div>
  );
}
