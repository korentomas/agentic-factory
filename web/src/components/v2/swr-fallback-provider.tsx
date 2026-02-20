"use client";

import { SWRConfig } from "swr";

interface SWRFallbackProviderProps {
  fallback: Record<string, unknown>;
  children: React.ReactNode;
}

export function SWRFallbackProvider({
  fallback,
  children,
}: SWRFallbackProviderProps) {
  return <SWRConfig value={{ fallback }}>{children}</SWRConfig>;
}
