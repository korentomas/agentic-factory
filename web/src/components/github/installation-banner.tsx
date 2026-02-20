"use client";

import { useState, useEffect } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { X, Github } from "lucide-react";
import { cn } from "@/lib/utils";

const GITHUB_APP_URL =
  "https://github.com/apps/agentfactory-bot/installations/new";

const BANNER_DISMISSED_KEY = "lailatov_install_banner_dismissed";

interface GitHubInstallationBannerProps {
  hasRepos: boolean;
}

export function GitHubInstallationBanner({
  hasRepos,
}: GitHubInstallationBannerProps) {
  const [dismissed, setDismissed] = useState(false);
  const [isNewUser, setIsNewUser] = useState(false);

  useEffect(() => {
    const wasDismissed = localStorage.getItem(BANNER_DISMISSED_KEY);
    if (wasDismissed) {
      setDismissed(true);
    } else if (!hasRepos) {
      setIsNewUser(true);
    }
  }, [hasRepos]);

  if (hasRepos || dismissed) {
    return null;
  }

  const handleDismiss = () => {
    setDismissed(true);
    localStorage.setItem(BANNER_DISMISSED_KEY, "true");
  };

  return (
    <Card
      className={cn(
        "border-border bg-card relative",
        isNewUser && "border-primary/30 shadow-md",
      )}
    >
      <CardContent className="flex items-center gap-4 p-4">
        <div className="bg-primary/10 flex h-10 w-10 shrink-0 items-center justify-center rounded-full">
          <Github className="text-primary h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="text-foreground text-sm font-medium">
            {isNewUser
              ? "Welcome to LailaTov! Connect your repos"
              : "Connect your repositories"}
          </h3>
          <p className="text-muted-foreground mt-0.5 text-xs">
            Install our GitHub App to grant access to your repositories and
            enable autonomous development.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            variant="brand"
            size="sm"
            onClick={() => window.open(GITHUB_APP_URL, "_blank")}
          >
            Install App
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className="h-8 w-8"
            onClick={handleDismiss}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
