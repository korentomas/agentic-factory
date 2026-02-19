import { NextRequest, NextResponse } from "next/server";
import { getStripe } from "@/lib/stripe";

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
      const _session = event.data.object;
      // TODO: Activate subscription for user
      break;
    }
    case "customer.subscription.updated": {
      const _subscription = event.data.object;
      // TODO: Handle subscription plan changes
      break;
    }
    case "customer.subscription.deleted": {
      const _subscription = event.data.object;
      // TODO: Deactivate subscription for user
      break;
    }
    default:
      break;
  }

  return NextResponse.json({ received: true });
}
