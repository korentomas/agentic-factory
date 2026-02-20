import type { Metadata } from "next";
import React, { Suspense } from "react";
import { NuqsAdapter } from "nuqs/adapters/next/app";
import { SessionProvider } from "@/components/session-provider";

export const metadata: Metadata = {
  title: "Chat — LailaTov",
  description: "Create and manage autonomous coding tasks",
};

export default function ChatLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <NuqsAdapter>
      <SessionProvider>
        <Suspense fallback={<div className="bg-background flex h-screen items-center justify-center"><span className="text-muted-foreground">Loading...</span></div>}>{children}</Suspense>
      </SessionProvider>
    </NuqsAdapter>
  );
}
