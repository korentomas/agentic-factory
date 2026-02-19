import { cn } from "@/lib/utils";

interface BentoGridProps {
  children: React.ReactNode;
  className?: string;
}

export function BentoGrid({ children, className }: BentoGridProps) {
  return (
    <div
      className={cn(
        "grid grid-cols-1 gap-[var(--space-6)] md:grid-cols-2 lg:grid-cols-3",
        className
      )}
    >
      {children}
    </div>
  );
}

interface BentoCellProps {
  children: React.ReactNode;
  className?: string;
  span?: "1" | "2" | "row";
}

export function BentoCell({ children, className, span = "1" }: BentoCellProps) {
  return (
    <div
      className={cn(
        "rounded-[var(--radius-xl)] bg-[var(--color-bg-surface)] p-[var(--space-8)]",
        "shadow-[var(--shadow-sm)] transition-shadow duration-[var(--duration-normal)]",
        "hover:shadow-[var(--shadow-md)]",
        span === "2" && "md:col-span-2",
        span === "row" && "md:col-span-2 lg:col-span-3",
        className
      )}
    >
      {children}
    </div>
  );
}
