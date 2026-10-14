# Meetbeatz — Android app

An Android app for **[meetbeatz.com](https://meetbeatz.com)**: the beat store, the online
recording booth and studio bookings, in a launcher icon.

It is a **Trusted Web Activity** — the site itself runs inside the app, full screen, with
no browser UI — plus the native pieces a browser cannot provide: a splash screen, a
launcher icon drawn from the same artwork as the site, long-press shortcuts, background
downloads for purchased files, microphone and camera for the recording booth, delegated
notifications and a branded offline screen.

| | |
| --- | --- |
| **Install it on a phone** | `git tag v1.0.0 && git push origin v1.0.0` → tap the APK link on the [latest release](releases/latest) (no login, no unzipping) |
| **Get an APK by hand** | Actions → Android → the latest run → Artifacts → `meetbeatz-debug-apk` |
| **See it in a browser** | `tools/preview_web_patch.sh`, or open the site on a phone and choose **Install app** |
| **Read this first** | [`docs/ANDROID_APP.md`](docs/ANDROID_APP.md) — build, sign, verify, publish, troubleshoot |
| **Website side** | [`web/README-ANDROID.md`](web/README-ANDROID.md) — the manifest, service worker and asset links the site needs |
| **Publish to Play** | Actions → **Publish to Google Play** → Run workflow — the button appears once this branch is merged; before that, `git tag v1.0.0 && git push origin v1.0.0` runs the same job (one-time setup: [`docs/ANDROID_APP.md` §5](docs/ANDROID_APP.md#5-publishing-to-google-play)) |
| **Play Store listing** | [`docs/play/store-listing.md`](docs/play/store-listing.md) — listing copy, data safety, screenshots, checklist |

## Quick start

```bash
# Build locally (needs JDK 17 + Android SDK platform 36)
cd android && ./gradlew assembleDebug        # → app/build/outputs/apk/debug/app-debug.apk

# Static checks — no Android SDK required, plain Python 3
python3 tools/ci_check.py

# Prove the website patch is safe to deploy: applies it to a clean clone of the site
# and runs that project's own typecheck and production build (~1 minute)
tools/verify_web_patch.sh

# Look at it: same patch, plus an embedded Postgres and a real demo storefront
# → http://localhost:3000 (producer sign-in at /admin/login)
tools/preview_web_patch.sh

# Rebuild the brand artwork from tools/source/logo.png (needs Pillow)
python3 tools/make_brand_assets.py

# Fingerprint → assetlinks.json, so links open without a browser bar
python3 tools/make_assetlinks.py --print-only

# Play upload key + secrets, then a version bump before each release
tools/make_upload_key.sh
tools/bump_version_code.sh --name 1.1.0

# Apply the website change and open the pull request on meetbeatz.com's repository
tools/apply_web_patch.sh --fingerprint AA:BB:CC:…
```

## What is in here

```
android/                        the app: Kotlin, Gradle, android-browser-helper 2.7.4
  app/src/main/kotlin/…           two activities: the TWA and the WebView fallback
  app/src/main/res/               launcher icons, splash, shortcuts, colours, themes
web/                            the change meetbeatz.com needs, as an applyable patch
  patches/                        the patch, plus the layout edit it is built from
  public/, src/                   the same files, editable here first
tools/                          brand assets, asset links, checks, patch plumbing
docs/                           app documentation and Play Store material
.github/workflows/android.yml   builds both APKs on every push
```

## How the pieces fit together

```
        ┌───────────────────────────┐
        │  MeetbeatzLauncherActivity│  Android launcher icon, shortcuts, deep links
        └─────────────┬─────────────┘
                      │ verified against /.well-known/assetlinks.json
        ┌─────────────▼─────────────┐
        │  Chrome (Trusted Web      │  the site, full screen, no browser UI
        │  Activity)                │  splash · downloads · notifications · mic
        └─────────────┬─────────────┘
                      │ no TWA provider on this device?
        ┌─────────────▼─────────────┐
        │  MeetbeatzWebViewActivity │  native shell: DownloadManager, permissions,
        └───────────────────────────┘  file picker, offline screen, payment windows
                      │
        ┌─────────────▼─────────────┐
        │  meetbeatz.com            │  beats, checkout, recording booth, bookings
        └───────────────────────────┘  (unchanged — the app is a client of it)
```

The website keeps working on its own; the app is a client of it. That is why a price
change, a new beat or a copy fix needs no app release — only a change to the icon, the
manifest or the shell itself does.

## Honest status

**It builds.** Every push runs `assembleDebug` and `assembleRelease` — Kotlin, resource
linking and R8 minification included — and attaches installable APKs to the run. The app
has **not been run on a phone**, so the things that need a real device (splash screen,
verified deep links, downloads, microphone capture, delegated notifications) are listed
with what to check in §6 of [`docs/ANDROID_APP.md`](docs/ANDROID_APP.md#6-when-something-looks-wrong).
That file's last section says exactly what is verified, how, and what is not.
