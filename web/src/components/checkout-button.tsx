"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

interface CheckoutButtonProps {
  planId: string;
  highlighted?: boolean;
  children: React.ReactNode;
  className?: string;
}

export function CheckoutButton({
  planId,
  highlighted = false,
  children,
  className,
}: CheckoutButtonProps) {
  const [loading, setLoading] = useState(false);

  async function handleClick() {
    setLoading(true);
    try {
      const res = await fetch("/api/stripe/checkout", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ planId }),
      });

      if (res.status === 401) {
        window.location.href = `/login?plan=${planId}`;
        return;
      }

      const data = await res.json();
      if (data.url) {
        window.location.href = data.url;
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={loading}
      className={cn(
        "w-full block rounded-md py-3 text-center text-sm font-medium",
        "transition-colors duration-[var(--duration-fast)]",
        highlighted
          ? "bg-card text-primary hover:bg-background"
          : "bg-primary text-primary-foreground hover:bg-primary/90",
        loading && "opacity-50 cursor-not-allowed",
        className,
      )}
    >
      {loading ? "Redirecting..." : children}
    </button>
  );
}
