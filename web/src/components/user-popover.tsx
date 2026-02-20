"use client";

import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import Link from "next/link";
import { BarChart3, LogOut, Settings } from "lucide-react";
import { useSession, signOut } from "next-auth/react";
import { cn } from "@/lib/utils";
import { useState } from "react";

interface UserPopoverProps {
  className?: string;
}

function getInitials(name: string | null | undefined): string {
  if (!name) return "?";
  return name
    .split(" ")
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

export function UserPopover({ className }: UserPopoverProps) {
  const { data: session, status } = useSession();
  const [isSigningOut, setIsSigningOut] = useState(false);

  if (status === "loading") {
    return (
      <Button
        variant="ghost"
        size="sm"
        disabled
        className={cn("h-8 w-8 rounded-full p-0", className)}
      >
        <div className="bg-muted h-6 w-6 animate-pulse rounded-full" />
      </Button>
    );
  }

  if (!session?.user) {
    return null;
  }

  const { user } = session;

  const handleSignOut = async () => {
    setIsSigningOut(true);
    await signOut({ callbackUrl: "/" });
  };

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className={cn(
            "hover:bg-accent h-8 w-8 rounded-full p-0",
            className,
          )}
        >
          <Avatar className="h-6 w-6">
            <AvatarImage
              src={user.image ?? undefined}
              alt={user.name ?? "User"}
            />
            <AvatarFallback className="text-[10px]">
              {getInitials(user.name)}
            </AvatarFallback>
          </Avatar>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-0" align="end">
        <div className="p-4">
          <div className="mb-3 flex items-center gap-3">
            <Avatar className="h-10 w-10">
              <AvatarImage
                src={user.image ?? undefined}
                alt={user.name ?? "User"}
              />
              <AvatarFallback>{getInitials(user.name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 flex-1">
              <div className="text-foreground truncate text-sm font-medium">
                {user.name}
              </div>
              <div className="text-muted-foreground truncate text-xs">
                {user.email}
              </div>
            </div>
          </div>
          <Separator className="mb-1" />
          <Link
            href="/analytics"
            className="flex w-full items-center rounded-md px-2 py-2 text-sm text-foreground transition-colors hover:bg-muted"
          >
            <BarChart3 className="mr-2 h-4 w-4" />
            Analytics
          </Link>
          <Link
            href="/chat/settings"
            className="flex w-full items-center rounded-md px-2 py-2 text-sm text-foreground transition-colors hover:bg-muted"
          >
            <Settings className="mr-2 h-4 w-4" />
            Settings
          </Link>
          <Separator className="my-1" />
          <Button
            variant="ghost"
            className="w-full justify-start text-red-600 hover:bg-red-50 hover:text-red-700 dark:text-red-400 dark:hover:bg-red-950/50 dark:hover:text-red-300"
            onClick={handleSignOut}
            disabled={isSigningOut}
          >
            <LogOut className="mr-2 h-4 w-4" />
            {isSigningOut ? "Signing out..." : "Sign out"}
          </Button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
