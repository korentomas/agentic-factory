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
        "flex flex-col rounded-xl p-8",
        "transition-shadow duration-[var(--duration-normal)]",
        highlighted
          ? "bg-primary text-primary-foreground shadow-lg"
          : "bg-card shadow-sm hover:shadow-md"
      )}
    >
      <div className="mb-6">
        <h3 className="text-lg font-medium">{name}</h3>
        <p
          className={cn(
            "mt-2 text-sm",
            highlighted
              ? "text-primary-foreground/70"
              : "text-muted-foreground"
          )}
        >
          {description}
        </p>
      </div>

      <div className="mb-6">
        <span className="text-4xl font-semibold tracking-tight">
          {price}
        </span>
        <span
          className={cn(
            "text-sm",
            highlighted
              ? "text-primary-foreground/70"
              : "text-muted-foreground"
          )}
        >
          {period}
        </span>
      </div>

      <ul className="mb-8 flex-1 space-y-3">
        {features.map((feature) => (
          <li
            key={feature}
            className={cn(
              "flex items-start gap-2 text-sm",
              highlighted
                ? "text-primary-foreground/90"
                : "text-muted-foreground"
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
            "block rounded-md py-3 text-center text-sm font-medium",
            "transition-colors duration-[var(--duration-fast)]",
            highlighted
              ? "bg-card text-primary hover:bg-background"
              : "bg-primary text-primary-foreground hover:bg-primary/90"
          )}
        >
          {cta}
        </a>
      )}
    </div>
  );
}
