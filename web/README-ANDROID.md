# The website side of the Android app

The app is a **Trusted Web Activity**: it renders meetbeatz.com in the device's own
browser engine, with no browser UI, and adds the parts a browser cannot — a launcher
icon, a splash screen, long-press shortcuts, background downloads and delegated
notifications. Nothing is duplicated: the beat store, checkout, the recording booth
and the studio booking page are the same pages, from the same origin, with the same
session.

Three things have to exist **on meetbeatz.com** for that to work, and they live in this
folder as a patch because this session could not write to the website repository.

| What | Where it ends up | Why the app needs it |
| --- | --- | --- |
| `public/manifest.webmanifest` + `public/icons/*` | `meetbeatz.com/manifest.webmanifest`, `/icons/*` | Installability, and the name, theme colour, icon and shortcuts the app shows. |
| `public/sw.js` + `public/offline.html` | `meetbeatz.com/sw.js`, `/offline.html` | A branded offline page instead of the browser's grey error page, plus the push handlers. |
| `public/.well-known/assetlinks.json` | `meetbeatz.com/.well-known/assetlinks.json` | Proof that the app is owned by the same people as the domain. Without it the app runs, but with the browser's address bar on top. |
| `src/app/layout.tsx` (edit) | the root layout | Links the manifest, sets the ink theme colour, mounts the service-worker registrar. |
| `src/db/schema.ts` (edit) | `admins.push_subscription`, `customers.push_subscription` | Where `/api/push/subscribe` records a device. Nullable text columns, so the schema sync that runs as part of `npm run build` adds them on the next deploy. |

## Applying it

Two scripts, both runnable from this repository:

```bash
# 1. Fold web/** into one patch against the site's main branch (only needed
#    after editing anything under web/).
tools/make_web_patch.sh

# 2. On a machine authenticated as the site's owner: clone, apply, push, open a PR.
tools/apply_web_patch.sh --fingerprint AA:BB:CC:…
```

`apply_web_patch.sh` also takes `--dry-run` (apply and print the diff, change nothing)
and `--site /path/to/clone` (use a checkout you already have). If `gh` is unavailable it
pushes the branch and leaves the pull request to you.

The patch itself is at `web/patches/0001-make-site-installable-and-app-ready.patch`, and
`tools/make_web_patch.sh` re-verifies it applies cleanly to the site's current `main`
before writing it.

### Verify it before it is deployed

```bash
tools/verify_web_patch.sh          # clone → apply → npm install → tsc → npm run build
tools/verify_web_patch.sh --typecheck-only
```

This exists because of a real miss: the first version of this patch imported two helpers
the site does not export and wrote a column the schema did not have. Both are type errors,
both would have failed `npm run build` on the deploy, and the Android build could not
notice — the app only talks to the deployed site over HTTP. The script runs the site's own
gates against the patched tree, and `python3 tools/ci_check.py` carries a cheap offline
version of the same check on every push.

**Current status, as of the last run:** the patch applies to the site's `main`
(`90a7c07`), `tsc --noEmit` is clean, `npm run build` succeeds, and the four files Android
fetches (`/manifest.webmanifest`, `/sw.js`, `/offline.html`,
`/.well-known/assetlinks.json`) all answer 200 with the right content types.

## Step 1 — the certificate fingerprint (do this first)

`assetlinks.json` is committed with a **placeholder** fingerprint. Until it is replaced,
Android cannot verify the app and links open with a browser bar — the app works, it just
looks like a browser.

```bash
# Release key (what customers will install)
python3 tools/make_assetlinks.py \
    --keystore android/meetbeatz-release.jks --alias meetbeatz --password '…' \
    --out web/public/.well-known/assetlinks.json

# Or the Play Console's copy, which is what Play re-signs with:
#   Play Console → Test and release → App integrity → App signing key certificate → SHA-256
python3 tools/make_assetlinks.py --fingerprint AA:BB:… --append

# Your local debug key, if you want to test deep links from Android Studio
python3 tools/make_assetlinks.py --print-only
```

Then **deploy** the site and confirm:

```bash
curl -sI https://meetbeatz.com/manifest.webmanifest   # 200, application/manifest+json
curl -sI https://meetbeatz.com/sw.js                  # 200, javascript
curl -s  https://meetbeatz.com/.well-known/assetlinks.json

# On a device with the app installed:
adb shell pm get-app-links com.meetbeatz.app          # should list meetbeatz.com as enabled
```

Note that Play re-signs every release, so the **Play App Signing** fingerprint is the one
that matters for a store build. Listing both is normal and supported.

## Step 2 — push notifications

The service worker already carries the `push` and `notificationclick` handlers,
`src/app/api/push/subscribe/route.ts` stores a subscription against the signed-in admin
or customer, and the two nullable `push_subscription` columns it writes to are part of
this patch — the schema sync inside `npm run build` adds them on the first deploy, so
there is no migration step.

That leaves one piece: **a sender.** Every booking, order and message already funnels through
`notifyProducer()` in `src/lib/notifications.ts`, which makes it the one place worth
adding this:

```ts
// A reference sender. Add `npm i web-push` and set VAPID_PUBLIC_KEY /
// VAPID_PRIVATE_KEY / VAPID_SUBJECT in the environment.
import webpush from "web-push";

webpush.setVapidDetails(
  process.env.VAPID_SUBJECT!,
  process.env.VAPID_PUBLIC_KEY!,
  process.env.VAPID_PRIVATE_KEY!,
);

async function pushToDevice(stored: string | null, title: string, body: string, url: string) {
  if (!stored) return;
  try {
    await webpush.sendNotification(JSON.parse(stored), JSON.stringify({ title, body, url }));
  } catch (err) {
    // 404/410 means the device uninstalled the app or revoked the permission:
    // clear the column rather than retrying forever.
    if ((err as { statusCode?: number }).statusCode === 410) {
      // await db.update(...).set({ pushSubscription: null })...
    }
  }
}
```

The endpoint is an opaque HTTPS URL supplied by the browser's push service; only that
service can act on it, which is why the route stores it verbatim after checking the
scheme, and why deploying `assetlinks.json` is what ties that traffic to your app.

On the client, the subscription is created only when a customer taps something —
never on first load:

```ts
const permission = await Notification.requestPermission();
if (permission !== "granted") return;

const registration = await navigator.serviceWorker.ready;
const subscription = await registration.pushManager.subscribe({
  userVisibleOnly: true,
  applicationServerKey: process.env.NEXT_PUBLIC_VAPID_PUBLIC_KEY,
});

await fetch("/api/push/subscribe", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(subscription),
});
```

Until that sender exists, nobody calls `/api/push/subscribe`, the columns stay null and
nothing changes for anyone.

## If `/.well-known/assetlinks.json` 404s

Next serves everything in `public/` as-is, including dot-directories — **verified**: the
patched site was built and run here and all four files Android fetches answered 200 with
the right content types (`/manifest.webmanifest`, `/sw.js`, `/offline.html`,
`/.well-known/assetlinks.json`). If a future deploy ever refuses to serve the folder —
a CDN rule, a rewrites entry, or a host that hides dotfiles — the app can still verify by
serving it from a route handler instead:

```ts
// src/app/.well-known/assetlinks.json/route.ts
import { readFileSync } from "node:fs";

export const dynamic = "force-static";

export function GET() {
  return new Response(
    readFileSync("public/.well-known/assetlinks.json", "utf8"),
    { headers: { "Content-Type": "application/json" } },
  );
}
```

Verify with `curl -sI https://meetbeatz.com/.well-known/assetlinks.json` — it must be a
200 over HTTPS with no redirect, because Android does not follow redirects when it checks
the file.

## What the service worker does and does not cache

Worth knowing before editing `public/sw.js`, because it ships to a live storefront:

- **Never cached:** `/api/*`, `/admin*`, `/checkout*`, `/orders/*`, `/license/*`,
  `/account*`, `/cart`. These carry a session, a cart, an order or a licence key. A
  cached copy could be shown to the next person who opens the app on a shared phone.
- **Network-first:** navigations. Online, prices and stock are always fresh.
- **Cache-first:** `/_next/static/*`, `/icons/*`, `/images/*`, `/audio/*` — filenames
  that carry a content hash or ship with the build.
- **Never touched:** any non-GET request. Checkout is a POST.

Bump `VERSION` at the top of `sw.js` to discard the older caches on the next visit.

## What the site should keep doing

- Keep `theme_color` and `background_color` at the site's ink black (`#050506`) so the
  splash, the status bar and the page agree.
- Keep the manifest's `start_url` in `scope`; the app launches that URL.
- If the header ever gains `padding-top: env(safe-area-inset-top)`, the
  `viewport-fit=cover` note in `src/app/layout.tsx` can be turned back on for a true
  edge-to-edge render. Until then it is deliberately off, so the logo never slides under
  the status bar.
