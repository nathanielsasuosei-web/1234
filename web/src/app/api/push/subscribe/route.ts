import { db } from "@/db";
import { admins, customers } from "@/db/schema";
import { getAdminSession } from "@/lib/auth";
import { getCustomerSession } from "@/lib/customer-auth";
import { eq } from "drizzle-orm";

export const dynamic = "force-dynamic";

/**
 * Stores a Web Push subscription for the Meetbeatz Android app.
 *
 * A Trusted Web Activity is the site itself, so its notifications are the site's
 * notifications: Chrome delivers them through the app's `DelegationService`, and
 * tapping one reopens the app instead of a browser tab. What is missing without
 * this endpoint is a place to keep the subscription — the service worker has the
 * push handler (public/sw.js) but nothing records where to send.
 *
 * Deliberately small and additive: no new dependency, and no delivery code.
 *
 *   - The subscription is stored on `admins` for the producer's own devices and on
 *     `customers` for buyers. Both columns (`push_subscription`) ship in the same
 *     patch as this file and are nullable, so the schema push the build already runs
 *     adds them on the next deploy and nothing else has to change.
 *   - Sending is left to whatever the producer already uses: `notifyProducer()` in
 *     src/lib/notifications.ts is the single place every booking, order and message
 *     already flows through, so it is the natural place to read these rows and POST
 *     to each subscription's endpoint with VAPID keys.
 *
 * Until a sender exists this endpoint is harmless: with no caller it stores nothing,
 * and the site works exactly as before.
 */

type SubscriptionBody = {
  endpoint?: unknown;
  keys?: { p256dh?: unknown; auth?: unknown };
  topic?: unknown;
};

function parseSubscription(payload: SubscriptionBody) {
  const endpoint = String(payload.endpoint ?? "").trim();
  const p256dh = String(payload.keys?.p256dh ?? "").trim();
  const auth = String(payload.keys?.auth ?? "").trim();

  if (!endpoint.startsWith("https://") || !p256dh || !auth) return null;
  // Nothing else about a subscription is trusted: the endpoint is an opaque HTTPS
  // URL supplied by the browser, and only the push service can act on it.
  return { endpoint, p256dh, auth, topic: String(payload.topic ?? "").slice(0, 120) };
}

export async function POST(req: Request) {
  const subscription = parseSubscription((await req.json().catch(() => ({}))) as SubscriptionBody);
  if (!subscription) {
    return Response.json({ error: "That is not a valid push subscription." }, { status: 400 });
  }

  const stored = JSON.stringify({
    endpoint: subscription.endpoint,
    keys: { p256dh: subscription.p256dh, auth: subscription.auth },
    savedAt: new Date().toISOString(),
    topic: subscription.topic || undefined,
  });

  // Producer first: a signed-in admin device is what a booking alert should reach.
  try {
    const admin = await getAdminSession();
    if (admin) {
      await db.update(admins).set({ pushSubscription: stored }).where(eq(admins.id, admin.id));
      return Response.json({ ok: true, audience: "admin" });
    }
  } catch (err) {
    console.warn("[api/push/subscribe] admin save skipped", err);
  }

  try {
    const customer = await getCustomerSession();
    if (customer) {
      await db
        .update(customers)
        .set({ pushSubscription: stored })
        .where(eq(customers.id, customer.id));
      return Response.json({ ok: true, audience: "customer" });
    }
  } catch (err) {
    console.warn("[api/push/subscribe] customer save skipped", err);
  }

  // Anonymous visitors get a 200 with `stored: false`: the permission prompt is a
  // deliberate choice by the customer and should not look like a failure here.
  return Response.json({ ok: true, stored: false, audience: "anonymous" });
}
