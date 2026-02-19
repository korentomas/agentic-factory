import { cn } from "@/lib/utils";
import { CheckoutButton } from "@/components/checkout-button";

interface PricingCardProps {
  name: string;
  price: string;
  period: string;
  description: string;
  features: string[];
  cta: string;
  highlighted?: boolean;
  href: string;
  planId?: string;
}

export function PricingCard({
  name,
  price,
  period,
  description,
  features,
  cta,
  highlighted = false,
  href,
  planId,
}: PricingCardProps) {
  return (
    <div
      className={cn(
        "flex flex-col rounded-[var(--radius-xl)] p-[var(--space-8)]",
        "transition-shadow duration-[var(--duration-normal)]",
        highlighted
          ? "bg-[var(--color-accent)] text-[var(--color-text-inverse)] shadow-[var(--shadow-lg)]"
          : "bg-[var(--color-bg-surface)] shadow-[var(--shadow-sm)] hover:shadow-[var(--shadow-md)]"
      )}
    >
      <div className="mb-[var(--space-6)]">
        <h3 className="text-[var(--text-lg)] font-medium">{name}</h3>
        <p
          className={cn(
            "mt-[var(--space-2)] text-[var(--text-sm)]",
            highlighted
              ? "text-[var(--color-text-inverse)]/70"
              : "text-[var(--color-text-secondary)]"
          )}
        >
          {description}
        </p>
      </div>

      <div className="mb-[var(--space-6)]">
        <span className="text-[var(--text-4xl)] font-semibold tracking-tight">
          {price}
        </span>
        <span
          className={cn(
            "text-[var(--text-sm)]",
            highlighted
              ? "text-[var(--color-text-inverse)]/70"
              : "text-[var(--color-text-muted)]"
          )}
        >
          {period}
        </span>
      </div>

      <ul className="mb-[var(--space-8)] flex-1 space-y-[var(--space-3)]">
        {features.map((feature) => (
          <li
            key={feature}
            className={cn(
              "flex items-start gap-[var(--space-2)] text-[var(--text-sm)]",
              highlighted
                ? "text-[var(--color-text-inverse)]/90"
                : "text-[var(--color-text-secondary)]"
            )}
          >
            <span className="mt-0.5 text-[var(--color-success)]">&#10003;</span>
            {feature}
          </li>
        ))}
      </ul>

      {planId ? (
        <CheckoutButton planId={planId} highlighted={highlighted}>
          {cta}
        </CheckoutButton>
      ) : (
        <a
          href={href}
          className={cn(
            "block rounded-[var(--radius-md)] py-[var(--space-3)] text-center text-[var(--text-sm)] font-medium",
            "transition-colors duration-[var(--duration-fast)]",
            highlighted
              ? "bg-[var(--color-bg-surface)] text-[var(--color-accent)] hover:bg-[var(--color-bg)]"
              : "bg-[var(--color-accent)] text-[var(--color-text-inverse)] hover:bg-[var(--color-accent-hover)]"
          )}
        >
          {cta}
        </a>
      )}
    </div>
  );
}
