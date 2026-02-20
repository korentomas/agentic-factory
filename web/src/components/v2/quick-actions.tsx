"use client";

import { Dispatch, SetStateAction } from "react";
import { Card, CardDescription, CardHeader, CardTitle } from "../ui/card";
import { Bug, Plus, TestTube, Paintbrush } from "lucide-react";

const QUICK_ACTIONS = [
  {
    title: "Fix a Bug",
    description: "Describe the bug and let the agent diagnose and fix it.",
    prompt:
      "I found a bug: [describe the issue]. Please investigate the root cause and submit a fix with tests.",
    icon: Bug,
  },
  {
    title: "Add a Feature",
    description: "Describe the feature and the agent will implement it.",
    prompt:
      "Please implement the following feature: [describe the feature]. Follow existing patterns in the codebase and add tests.",
    icon: Plus,
  },
  {
    title: "Write Tests",
    description: "Generate test coverage for existing code.",
    prompt:
      "Please add comprehensive tests for [module/file]. Cover edge cases and follow existing test patterns.",
    icon: TestTube,
  },
  {
    title: "Refactor Code",
    description: "Clean up and improve code quality.",
    prompt:
      "Please refactor [module/file] to improve readability and maintainability. Keep behavior identical and ensure tests pass.",
    icon: Paintbrush,
  },
] as const;

interface QuickActionsProps {
  setQuickActionPrompt: Dispatch<SetStateAction<string>>;
}

export function QuickActions({ setQuickActionPrompt }: QuickActionsProps) {
  return (
    <div>
      <h2 className="text-foreground mb-3 text-base font-semibold">
        Quick Actions
      </h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {QUICK_ACTIONS.map((action) => (
          <Card
            key={action.title}
            onClick={() => setQuickActionPrompt(action.prompt)}
            className="border-border bg-card hover:bg-muted/30 dark:hover:bg-muted/20 hover:shadow-primary/2 cursor-pointer py-3 transition-all duration-200 hover:shadow-sm"
          >
            <CardHeader className="px-3">
              <CardTitle className="text-foreground flex items-center gap-2 text-sm">
                <action.icon className="text-muted-foreground h-4 w-4" />
                {action.title}
              </CardTitle>
              <CardDescription className="text-muted-foreground text-xs">
                {action.description}
              </CardDescription>
            </CardHeader>
          </Card>
        ))}
      </div>
    </div>
  );
}
