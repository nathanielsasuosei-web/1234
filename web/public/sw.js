/*
 * Meetbeatz service worker.
 *
 * This file is deliberately small, dependency-free and conservative: it ships to a
 * live storefront, so the rules are written around what must never happen rather
 * than around maximum cache hits.
 *
 *   - Never cached, never served from cache: /api/*, /admin*, /checkout*,
 *     /orders/*, /license/*, /account*, /cart. These carry a customer's session,
 *     their cart, their order, or their licence key. A cached copy of one of those
 *     could be shown to the next person who opens the app on a shared phone.
 *   - Navigations are network-first: online, the customer always gets fresh
 *     prices and stock; offline, they get the last copy of that page they saw, and
 *     failing that the branded offline page below.
 *   - Build output and icons are cache-first, because a file under
 *     /_next/static/ has a content hash in its name — it can never be stale.
 *   - POST/PUT/PATCH/DELETE are never touched at all: checkout is a POST.
 *
 * It also carries the two push handlers, so a notification sent by the site opens
 * the page it is about and focuses the app instead of starting a second copy.
 */

const VERSION = "v1";
const SHELL_CACHE = `meetbeatz-shell-${VERSION}`;
const ASSET_CACHE = `meetbeatz-assets-${VERSION}`;
const PAGE_CACHE = `meetbeatz-pages-${VERSION}`;
const KNOWN_CACHES = [SHELL_CACHE, ASSET_CACHE, PAGE_CACHE];

const OFFLINE_URL = "/offline.html";
const SHELL_ASSETS = [
  OFFLINE_URL,
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
];

/** Paths that must always come from the network. */
const NEVER_CACHE = [
  /^\/api\//,
  /^\/admin/,
  /^\/checkout/,
  /^\/orders\//,
  /^\/license\//,
  /^\/account/,
  /^\/cart/,
];

const isPrivate = (pathname) => NEVER_CACHE.some((pattern) => pattern.test(pathname));

/** Files whose name contains a build hash, so the bytes can never change. */
const isImmutable = (pathname) =>
  pathname.startsWith("/_next/static/") ||
  pathname.startsWith("/icons/") ||
  pathname.startsWith("/images/") ||
  pathname.startsWith("/audio/");

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(SHELL_CACHE);
      // Individual failures must not fail the whole install: a missing icon would
      // otherwise leave the site with no service worker at all.
      await Promise.all(
        SHELL_ASSETS.map((asset) => cache.add(asset).catch(() => undefined)),
      );
      await self.skipWaiting();
    })(),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const names = await caches.keys();
      await Promise.all(
        names
          .filter((name) => name.startsWith("meetbeatz-") && !KNOWN_CACHES.includes(name))
          .map((name) => caches.delete(name)),
      );
      if (self.registration.navigationPreload) {
        // Serve the network's response while the page is still being parsed.
        await self.registration.navigationPreload.disable();
      }
      await self.clients.claim();
    })(),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  if (request.method !== "GET") return;

  const url = new URL(request.url);

  // Third-party requests (Paystack's checkout frame, Google's tag manager, the
  // WhatsApp link) are none of this worker's business.
  if (url.origin !== self.location.origin) return;

  if (isPrivate(url.pathname)) return;

  if (request.mode === "navigate") {
    event.respondWith(handleNavigation(request));
    return;
  }

  if (isImmutable(url.pathname)) {
    event.respondWith(cacheFirst(request, ASSET_CACHE));
  }
});

/**
 * Network-first navigation with three fallbacks: the cached copy of the exact page,
 * the cached copy of the same section (so an offline tap on a beat still lands on
 * the store), and finally the offline page.
 */
async function handleNavigation(request) {
  try {
    const response = await fetch(request);
    if (response && response.ok && response.type === "basic") {
      const copy = response.clone();
      caches
        .open(PAGE_CACHE)
        .then((cache) => cache.put(request, copy))
        .catch(() => undefined);
    }
    return response;
  } catch (_) {
    const cached = await caches.match(request, { ignoreSearch: true });
    if (cached) return cached;

    const shell = await caches.open(SHELL_CACHE);
    const offline = await shell.match(OFFLINE_URL);
    if (offline) return offline;

    return new Response("You are offline.", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  const response = await fetch(request);
  if (response && response.ok && response.type === "basic") {
    const copy = response.clone();
    caches
      .open(cacheName)
      .then((cache) => cache.put(request, copy))
      .catch(() => undefined);
  }
  return response;
}

/* ------------------------------------------------------------------ push ------ */

self.addEventListener("push", (event) => {
  let payload = {};
  try {
    payload = event.data ? event.data.json() : {};
  } catch (_) {
    payload = { body: event.data ? event.data.text() : "" };
  }

  const title = payload.title || "Meetbeatz";
  const options = {
    body: payload.body || "",
    icon: payload.icon || "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    // Anything the producer sends is about one order, one licence or one slot, so
    // replacing a notification of the same kind beats stacking duplicates.
    tag: payload.tag || "meetbeatz",
    renotify: true,
    data: { url: payload.url || "/account" },
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = new URL(event.notification.data?.url || "/", self.location.origin).href;

  event.waitUntil(
    (async () => {
      const clients = await self.clients.matchAll({
        type: "window",
        includeUncontrolled: true,
      });

      for (const client of clients) {
        if (client.url.startsWith(self.location.origin) && "focus" in client) {
          await client.navigate(target).catch(() => undefined);
          return client.focus();
        }
      }

      return self.clients.openWindow(target);
    })(),
  );
});
