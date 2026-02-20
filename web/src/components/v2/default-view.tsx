"use client";

import { useState, useMemo } from "react";
import Image from "next/image";
import useSWR from "swr";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Settings,
  BookOpen,
  CheckCircle2,
  Circle,
  ExternalLink,
  ArrowUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { ThreadCard, ThreadCardLoading } from "./thread-card";
import { TerminalInput } from "./terminal-input";
import { QuickActions } from "./quick-actions";
import { AppHeader } from "./app-header";
import { Toaster } from "sonner";
import { toThreadMetadata, fetcher } from "./thread-data";
import type { TaskThreadRow } from "./thread-data";
import NextLink from "next/link";

const GITHUB_APP_INSTALL_URL =
  "https://github.com/apps/agentfactory-bot/installations/new";

/* ------------------------------------------------------------------ */
/*  Header utility buttons                                            */
/* ------------------------------------------------------------------ */

function OpenSettingsButton() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          asChild
          className="hover:bg-accent hover:text-accent-foreground size-6 rounded-md p-1 hover:cursor-pointer"
        >
          <NextLink href="/chat/settings">
            <Settings className="size-4" />
          </NextLink>
        </TooltipTrigger>
        <TooltipContent side="bottom">Settings</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

function OpenDocumentationButton() {
  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger
          asChild
          className="hover:bg-accent hover:text-accent-foreground size-6 rounded-md p-1 hover:cursor-pointer"
        >
          <a
            href="https://github.com/korentomas/agentic-factory"
            target="_blank"
            rel="noopener noreferrer"
          >
            <BookOpen className="size-4" />
          </a>
        </TooltipTrigger>
        <TooltipContent side="bottom">Documentation</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}

/* ------------------------------------------------------------------ */
/*  Onboarding checklist (replaces GitHubInstallationBanner)          */
/* ------------------------------------------------------------------ */

interface OnboardingStep {
  label: string;
  done: boolean;
  description: string;
  action?: { label: string; href: string };
}

function OnboardingChecklist({ hasThreads }: { hasThreads: boolean }) {
  const steps: OnboardingStep[] = [
    {
      label: "Sign in with GitHub",
      done: true, // always true if they see this component
      description: "Authenticated via GitHub OAuth",
    },
    {
      label: "Install the GitHub App",
      done: false,
      description: "Grant access to your repositories",
      action: { label: "Install", href: GITHUB_APP_INSTALL_URL },
    },
    {
      label: "Create your first task",
      done: hasThreads,
      description: hasThreads
        ? "You're all set!"
        : "Describe a task below, or open a GitHub issue",
    },
  ];

  const completedCount = steps.filter((s) => s.done).length;
  const progressPct = Math.round((completedCount / steps.length) * 100);

  return (
    <div className="border-border bg-card rounded-xl border p-5 shadow-sm">
      {/* Header row */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-foreground text-base font-semibold">
            Get started
          </h2>
          <p className="text-muted-foreground mt-0.5 text-xs">
            {completedCount} of {steps.length} steps complete
          </p>
        </div>

        {/* Progress bar */}
        <div className="bg-muted h-2 w-28 overflow-hidden rounded-full">
          <div
            className="bg-primary h-full rounded-full transition-all duration-300"
            style={{ width: `${progressPct}%` }}
          />
        </div>
      </div>

      {/* Steps */}
      <ol className="mt-4 space-y-3">
        {steps.map((step, i) => (
          <li key={i} className="flex items-start gap-3">
            {step.done ? (
              <CheckCircle2 className="text-primary mt-0.5 size-5 shrink-0" />
            ) : (
              <Circle className="text-muted-foreground mt-0.5 size-5 shrink-0" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span
                  className={`text-sm font-medium ${
                    step.done
                      ? "text-foreground"
                      : "text-muted-foreground"
                  }`}
                >
                  {step.label}
                </span>
                {step.action && !step.done && (
                  <a
                    href={step.action.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="bg-primary text-primary-foreground hover:bg-primary/90 inline-flex items-center gap-1 rounded-md px-2 py-0.5 text-xs font-medium transition-colors"
                  >
                    {step.action.label}
                    <ExternalLink className="size-3" />
                  </a>
                )}
              </div>
              <p className="text-muted-foreground text-xs">{step.description}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Empty thread state                                                */
/* ------------------------------------------------------------------ */

function EmptyThreadState({ logoSrc }: { logoSrc: string }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-10">
      <Image
        src={logoSrc}
        alt="LailaTov"
        width={48}
        height={48}
        className="h-12 w-12 opacity-60"
        style={{ imageRendering: "pixelated" }}
        unoptimized
      />
      <p className="text-muted-foreground text-center text-sm">
        Your first autonomous task is one description away
      </p>
      <ArrowUp className="text-muted-foreground/40 size-4 animate-bounce" />
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  DefaultView                                                       */
/* ------------------------------------------------------------------ */

interface DefaultViewProps {
  hasRepos: boolean;
}

export function DefaultView({ hasRepos }: DefaultViewProps) {
  const router = useRouter();
  const { resolvedTheme } = useTheme();
  const logoSrc = resolvedTheme === "dark" ? "/logo-dark.png" : "/logo.png";
  const [quickActionPrompt, setQuickActionPrompt] = useState("");

  const { data, isLoading } = useSWR<{ threads: TaskThreadRow[] }>(
    "/api/tasks",
    fetcher,
    { refreshInterval: 10_000 },
  );

  const threads = useMemo(
    () => (data?.threads ?? []).map(toThreadMetadata),
    [data],
  );

  const displayThreads = threads.slice(0, 4);
  const threadsLoading = isLoading && threads.length === 0;

  return (
    <div className="flex flex-1 flex-col">
      <Toaster />

      <AppHeader showBrand>
        <OpenDocumentationButton />
        <OpenSettingsButton />
      </AppHeader>

      {/* Main Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-4xl space-y-6 p-4">
          {/* Onboarding checklist -- shown only when repos are not connected */}
          {!hasRepos && (
            <OnboardingChecklist hasThreads={threads.length > 0} />
          )}

          {/* Terminal Input -- hero element */}
          <div className="pt-8">
            <TerminalInput
              placeholder="Describe your coding task or ask a question..."
              quickActionPrompt={quickActionPrompt}
              setQuickActionPrompt={setQuickActionPrompt}
            />
          </div>

          {/* Recent & Running Threads */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-foreground text-base font-semibold">
                Recent & Running Threads
              </h2>
              <Button
                variant="outline"
                size="sm"
                className="border-border text-muted-foreground hover:text-foreground h-7 text-xs"
                onClick={() => router.push("/chat/threads")}
              >
                View All
              </Button>
            </div>

            {threadsLoading || threads.length > 0 ? (
              <div className="grid gap-3 md:grid-cols-2">
                {threadsLoading && (
                  <>
                    <ThreadCardLoading />
                    <ThreadCardLoading />
                    <ThreadCardLoading />
                    <ThreadCardLoading />
                  </>
                )}
                {displayThreads.map((thread) => (
                  <ThreadCard key={thread.id} thread={thread} />
                ))}
              </div>
            ) : (
              <EmptyThreadState logoSrc={logoSrc} />
            )}
          </div>

          <QuickActions setQuickActionPrompt={setQuickActionPrompt} />
        </div>
      </div>
    </div>
  );
}
