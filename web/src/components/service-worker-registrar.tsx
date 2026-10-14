/*
 * Service worker registration for meetbeatz.com.
 *
 * Renders nothing — it exists so the site behaves as an installable Android app.
 * Two jobs, in order of importance:
 *
 *  1. **Offline shell.** The Android app is a Trusted Web Activity, which means the
 *     pages are the device's own browser engine, not this app. In a dead spot the
 *     browser would otherwise show its own grey error page. The worker serves the
 *     branded offline page instead (see public/sw.js for exactly what is and is not
 *     cached — nothing private, ever).
 *
 *  2. **Push notifications.** The push handlers live in public/sw.js. They are only
 *     exercised once a subscription exists, which this component never creates on its
 *     own: a notification permission prompt on the first page load is the fastest way
 *     to have a customer refuse it forever.
 *
 * Registration is skipped entirely inside the admin dashboard, so the producer's
 * session is never involved in updating a worker mid-upload.
 */
"use client";

import { useEffect } from "react";

export function ServiceWorkerRegistrar() {
  useEffect(() => {
    if (typeof window === "undefined" || !("serviceWorker" in navigator)) return;
    if (process.env.NODE_ENV !== "production") return;
    if (window.location.pathname.startsWith("/admin")) return;

    const register = () => {
      navigator.serviceWorker.register("/sw.js", { scope: "/" }).catch(() => {
        // A worker that fails to register must never affect the page: the site is
        // fully functional without it, just without offline support.
      });
    };

    // Registering after load keeps the worker off the critical path.
    if (document.readyState === "complete") register();
    else window.addEventListener("load", register, { once: true });

    return () => window.removeEventListener("load", register);
  }, []);

  return null;
}
