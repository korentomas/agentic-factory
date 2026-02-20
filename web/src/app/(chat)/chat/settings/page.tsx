"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { Github, LogOut, CreditCard, Cpu, ExternalLink } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Avatar,
  AvatarImage,
  AvatarFallback,
} from "@/components/ui/avatar";
import { AppHeader } from "@/components/v2/app-header";

const ENGINES = [
  { value: "claude-code", label: "Claude Code", description: "Anthropic's coding agent" },
  { value: "aider", label: "Aider", description: "Universal fallback via LiteLLM" },
] as const;

const MODELS = [
  { value: "claude-sonnet-4-20250514", label: "Claude Sonnet 4" },
  { value: "claude-opus-4-20250514", label: "Claude Opus 4" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "deepseek-chat", label: "DeepSeek V3" },
] as const;

const PLAN_TIERS = [
  { id: "starter", name: "Starter", price: "$49/mo", tasks: "30 tasks", repos: "3 repos", seats: "1 seat" },
  { id: "team", name: "Team", price: "$249/mo", tasks: "150 tasks", repos: "10 repos", seats: "10 seats" },
  { id: "enterprise", name: "Enterprise", price: "$999/mo", tasks: "500 tasks", repos: "Unlimited repos", seats: "Unlimited seats" },
] as const;

export default function SettingsPage() {
  const router = useRouter();
  const { data: session, status: sessionStatus } = useSession();
  const [selectedEngine, setSelectedEngine] = useState("claude-code");
  const [selectedModel, setSelectedModel] = useState("claude-sonnet-4-20250514");

  return (
    <div className="bg-background flex h-screen flex-col">
      <AppHeader showBackButton backHref="/chat" title="Settings" />

      {/* Content */}
      <div className="flex-1 overflow-auto">
        <div className="mx-auto max-w-3xl space-y-6 p-6">
          {/* GitHub Connection */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Github className="h-5 w-5" />
                GitHub Connection
              </CardTitle>
              <CardDescription>
                Your connected GitHub account and installation
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {sessionStatus === "loading" ? (
                <div className="bg-muted h-20 animate-pulse rounded-lg" />
              ) : session?.user ? (
                <div className="border-border bg-muted/30 flex items-center justify-between rounded-lg border p-4">
                  <div className="flex items-center gap-3">
                    <Avatar className="h-10 w-10">
                      <AvatarImage
                        src={session.user.image ?? undefined}
                        alt={session.user.name ?? "User"}
                      />
                      <AvatarFallback>
                        {session.user.name?.charAt(0) ?? "U"}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <p className="text-foreground font-medium">
                        {session.user.name}
                      </p>
                      <p className="text-muted-foreground text-sm">
                        {session.user.email}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="text-xs">
                      Connected
                    </Badge>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => signOut({ callbackUrl: "/" })}
                    >
                      <LogOut className="mr-1.5 h-3.5 w-3.5" />
                      Sign Out
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="border-border bg-muted/30 rounded-lg border p-6 text-center">
                  <Github className="text-muted-foreground mx-auto mb-3 h-10 w-10" />
                  <p className="text-foreground mb-1 font-medium">
                    Not connected
                  </p>
                  <p className="text-muted-foreground mb-4 text-sm">
                    Sign in with GitHub to connect your account
                  </p>
                  <Button onClick={() => router.push("/api/auth/signin")}>
                    <Github className="mr-1.5 h-4 w-4" />
                    Sign in with GitHub
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>

          <Separator />

          {/* Engine Preferences */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Cpu className="h-5 w-5" />
                Engine Preferences
              </CardTitle>
              <CardDescription>
                Choose the default engine and model for new tasks
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="space-y-2">
                <label className="text-foreground text-sm font-medium">
                  Default Engine
                </label>
                <Select value={selectedEngine} onValueChange={setSelectedEngine}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select engine" />
                  </SelectTrigger>
                  <SelectContent>
                    {ENGINES.map((engine) => (
                      <SelectItem key={engine.value} value={engine.value}>
                        <div className="flex flex-col">
                          <span>{engine.label}</span>
                          <span className="text-muted-foreground text-xs">
                            {engine.description}
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <label className="text-foreground text-sm font-medium">
                  Default Model
                </label>
                <Select value={selectedModel} onValueChange={setSelectedModel}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select model" />
                  </SelectTrigger>
                  <SelectContent>
                    {MODELS.map((model) => (
                      <SelectItem key={model.value} value={model.value}>
                        {model.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </CardContent>
          </Card>

          <Separator />

          {/* Subscription */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <CreditCard className="h-5 w-5" />
                Subscription
              </CardTitle>
              <CardDescription>
                Your current plan and usage limits
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-3">
                {PLAN_TIERS.map((plan) => {
                  const isCurrent = plan.id === "starter";
                  return (
                    <div
                      key={plan.id}
                      className={cn(
                        "border-border relative rounded-lg border p-4 transition-colors",
                        isCurrent
                          ? "border-primary/30 bg-primary/5"
                          : "bg-muted/30 hover:border-primary/20",
                      )}
                    >
                      {isCurrent && (
                        <Badge
                          variant="default"
                          className="absolute -top-2.5 right-3 text-xs"
                        >
                          Current
                        </Badge>
                      )}
                      <p className="text-foreground mb-1 font-semibold">
                        {plan.name}
                      </p>
                      <p className="text-primary mb-3 text-lg font-bold">
                        {plan.price}
                      </p>
                      <div className="text-muted-foreground space-y-1 text-xs">
                        <p>{plan.tasks}</p>
                        <p>{plan.repos}</p>
                        <p>{plan.seats}</p>
                      </div>
                      {!isCurrent && (
                        <Button
                          variant="outline"
                          size="sm"
                          className="mt-3 w-full text-xs"
                          onClick={() => router.push("/pricing")}
                        >
                          Upgrade
                          <ExternalLink className="ml-1 h-3 w-3" />
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
