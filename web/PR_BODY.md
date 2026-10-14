Groundwork for the **Meetbeatz Android app**. The app is a Trusted Web Activity — the website itself runs inside it — so what the app needs from this repository is identity, offline behaviour and three last pieces of plumbing, not new pages.

### What this adds

| File | Why |
| --- | --- |
| `public/manifest.webmanifest` | Name, ink theme colour, `standalone` display, the icon set, and four shortcuts (beat store, sound kits, record online, book studio). The Android app reads the same manifest for its label, splash colour and long-press shortcuts. |
| `public/icons/*` | 192 and 512 any-purpose icons, a maskable 512, and an Apple touch icon — all cut from the same logo master as the Android launcher icon, so the installed app and the browser tab finally match. |
| `public/sw.js` | The offline shell and the push handlers. Navigations are network-first; `/_next/static`, `/icons`, `/images` and `/audio` are cache-first because their filenames carry a build hash. `/api`, `/admin`, `/checkout`, `/orders`, `/license`, `/account` and `/cart` are **never** cached — a licence key or someone's cart must not be replayed to the next person who opens a shared phone. |
| `public/offline.html` | A self-contained branded offline page, so a dead spot shows Meetbeatz instead of the browser's grey error page. |
| `src/app/layout.tsx` | Links the manifest, exports `viewport` with `viewport-fit=cover` and `themeColor: #050506` — this is what removes the last seam between the app and the page — and mounts the registrar. |
| `src/components/service-worker-registrar.tsx` | Registers the worker after load, production only, never inside `/admin`. |
| `src/app/api/push/subscribe/route.ts` | Records a Web Push subscription against the signed-in admin or customer row. |
| `src/db/schema.ts` | The two nullable `push_subscription` columns that route writes to. The schema sync inside `npm run build` adds them on deploy, so there is no migration step. |
| `public/.well-known/assetlinks.json` | Android App Links verification. **The fingerprint in it is a placeholder** and must be replaced with the real signing certificate's SHA-256 before deploying, or links open with the browser's address bar on top. |

### What does not change

Nothing about any existing page, and no new dependency. If a browser has no service worker support — or the worker fails to register — every page renders exactly as it does today; the registrar deliberately swallows its own errors.

### One step left to switch push on

The handlers, the subscription endpoint and the database columns are all here. What is
missing is something to *send* with: a `fetch()` to each stored `subscription.endpoint`,
signed with VAPID keys, added in the one place every booking, order and message already
flows through — `notifyProducer()` in `src/lib/notifications.ts`. `web/README-ANDROID.md`
in the app repository has the reference implementation to paste in.

Until then nobody calls `/api/push/subscribe`, the columns stay null and nothing changes
for anyone.

### Deploy order

1. Replace the placeholder fingerprint in `public/.well-known/assetlinks.json`.
2. Deploy, then confirm these answer 200:
   - `https://meetbeatz.com/manifest.webmanifest`
   - `https://meetbeatz.com/sw.js`
   - `https://meetbeatz.com/.well-known/assetlinks.json`
3. Install the APK from the app repository's Actions artifacts.

Until step 1 is done the app still works fully — App Links simply are not verified, which is exactly what makes an unverified Trusted Web Activity show a browser address bar on top of the page.
