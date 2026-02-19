import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";
import {
  upsertSubscription,
  updateSubscriptionStatus,
} from "@/lib/db/queries";

export async function POST(request: NextRequest) {
  const body = await request.text();
  const signature = request.headers.get("stripe-signature");

  if (!signature) {
    return NextResponse.json({ error: "Missing signature" }, { status: 400 });
  }

  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!webhookSecret) {
    return NextResponse.json(
      { error: "Webhook secret not configured" },
      { status: 500 }
    );
  }

  const stripe = getStripe();

  let event;
  try {
    event = stripe.webhooks.constructEvent(body, signature, webhookSecret);
  } catch {
    return NextResponse.json({ error: "Invalid signature" }, { status: 400 });
  }

  switch (event.type) {
    case "checkout.session.completed": {
      const session = event.data.object;
      const userId = session.metadata?.userId;
      const planId = session.metadata?.planId;

      if (userId && session.subscription && session.customer) {
        const subscriptionId =
          typeof session.subscription === "string"
            ? session.subscription
            : session.subscription.id;
        const customerId =
          typeof session.customer === "string"
            ? session.customer
            : session.customer.id;

        const stripeSubscription =
          await stripe.subscriptions.retrieve(subscriptionId);

        await upsertSubscription({
          userId,
          stripeCustomerId: customerId,
          stripeSubscriptionId: subscriptionId,
          stripePriceId: stripeSubscription.items.data[0]?.price.id ?? "",
          planId: planId ?? "starter",
          status: "active",
          currentPeriodStart: new Date(
            stripeSubscription.current_period_start * 1000,
          ),
          currentPeriodEnd: new Date(
            stripeSubscription.current_period_end * 1000,
          ),
        });
      }
      break;
    }
    case "customer.subscription.updated": {
      const subscription = event.data.object;
      const status = subscription.cancel_at_period_end
        ? "cancelled"
        : "active";
      await updateSubscriptionStatus(subscription.id, status);
      break;
    }
    case "customer.subscription.deleted": {
      const subscription = event.data.object;
      await updateSubscriptionStatus(subscription.id, "cancelled");
      break;
    }
    default:
      break;
  }

  return NextResponse.json({ received: true });
}
