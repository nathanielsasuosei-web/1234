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
| **Get an APK** | Actions → Android → the latest run → Artifacts → `meetbeatz-debug-apk` |
| **Read this first** | [`docs/ANDROID_APP.md`](docs/ANDROID_APP.md) — build, sign, verify, publish, troubleshoot |
| **Website side** | [`web/README-ANDROID.md`](web/README-ANDROID.md) — the manifest, service worker and asset links the site needs |
| **Play Store** | [`docs/play/store-listing.md`](docs/play/store-listing.md) — listing copy, data safety, screenshots, checklist |

## Quick start

```bash
# Build locally (needs JDK 17 + Android SDK platform 36)
cd android && ./gradlew assembleDebug        # → app/build/outputs/apk/debug/app-debug.apk

# Static checks — no Android SDK required, plain Python 3
python3 tools/ci_check.py

# Rebuild the brand artwork from tools/source/logo.png (needs Pillow)
python3 tools/make_brand_assets.py

# Fingerprint → assetlinks.json, so links open without a browser bar
python3 tools/make_assetlinks.py --print-only

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

Written without an Android SDK in reach, so: every resource reference, manifest
invariant, icon density, brand asset and the website patch are **checked automatically**
(`tools/ci_check.py`, run first in CI), but **the app has not been compiled or run on a
device**. The first Actions run is the real compile — see the last section of
[`docs/ANDROID_APP.md`](docs/ANDROID_APP.md#what-has-and-has-not-been-verified) for what
is verified, how it was verified, and what to check on a phone.
