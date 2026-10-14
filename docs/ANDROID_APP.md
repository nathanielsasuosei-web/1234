# Meetbeatz for Android

An Android app for **meetbeatz.com** — the beat store, the studio booking page, the
online recording booth and Mobile Money checkout, in a launcher icon.

It is a **Trusted Web Activity** (TWA): the site itself is rendered by the device's
browser engine, edge to edge, with no browser UI. That is a deliberate choice, not a
shortcut — see [Why a TWA](#why-a-twa) — and it means one codebase, one deploy and one
set of prices. Beat previews with their player bar, the cart, Paystack checkout, the
colour adjuster and the producer's admin dashboard all behave exactly as they do on the
phone's browser, because they *are* the same pages.

```
android/              the app (Kotlin, Gradle, android-browser-helper 2.7.4)
  app/src/main/kotlin/com/meetbeatz/app/
    MeetbeatzLauncherActivity.kt   entry point: launches the TWA
    MeetbeatzWebViewActivity.kt    fallback shell when no TWA provider exists
  app/src/main/res/                icons, splash, shortcuts, themes
web/                  the change meetbeatz.com needs (patch + the files it contains)
tools/                brand assets, asset-links, static checks, patch plumbing
docs/                 this file, and the Play Store material
.github/workflows/    builds installable APKs on every push
```

---

## 1. Get an APK on a phone

### The fastest way — a tagged release (this is the one for a phone)

```bash
git tag v1.0.0 && git push origin v1.0.0
```

The **Release an installable build** workflow builds the debug APK, attaches it to a
GitHub Release and prints the download URL. Because the repository is public, that URL
needs no login, and it is an `.apk` rather than a zip — so the whole install happens on
the phone: open the link, tap the download, accept the unknown-source warning, install.

> Re-tagging the same version replaces the APK rather than failing, so fixing a build and
> re-pushing the tag is safe. Bump `versionCode` before a tag you intend to *ship* — Play
> refuses a code it has already seen, and `tools/bump_version_code.sh` does it.

> **Debug installs and Play installs cannot coexist.** The debug APK uses the package name
> `com.meetbeatz.app` but the debug key. Android refuses to upgrade an app across signing
> keys, so installing the Play build over a debug install fails with a bare "App not
> installed". Uninstall the debug copy first, then install from Play. Tests can be lost
> this way (a logged-in session is not — that lives in Chrome, not the app).

The same tag also runs **Publish to Google Play**, which skips itself with a warning until
the upload key exists (see §5). One tag, one version, both channels — and nothing turns
red just because Play has not been set up yet.

### The manual way — Actions artifacts

Every push to this repository builds the app and attaches it as a download:

1. Open the **Actions** tab → **Android** → the most recent green run.
2. Under **Artifacts**, download **meetbeatz-debug-apk** (about 4.7 MB).
3. Unzip it, copy `meetbeatz-1.0.0-1-debug.apk` to the phone (or send it by WhatsApp /
   email / Drive), tap it, and allow installation from that source when Android asks.
4. Open **Meetbeatz**. You should see the splash screen, then the store.

On the address bar: Android hides it only when `/.well-known/assetlinks.json` on your
domain lists the certificate the installed build was actually signed with. With the
placeholder fingerprint, or when the website patch is not deployed yet, the app still
runs but Chrome keeps its bar on screen. That is the expected state until §3 is done —
it is not a bug in the app, and a Play-installed build behaves the same way.

The first build takes about five minutes; later builds are faster. The release artifact
carries `signing-report.txt` — the SHA-256 of every signing certificate in the build, which
is the value that belongs in `assetlinks.json` (see §3). The debug keystore is cached
between runs, so the debug APK's fingerprint stays the same and can be used for testing
verified deep links.

Four artifacts come out of every push:

| Artifact | What it is |
| --- | --- |
| `meetbeatz-debug-apk` | ~4.7 MB, installable on any phone, the one to start with |
| `meetbeatz-release-apk` | the minified release build (~644 KB) plus `signing-report.txt` |
| `meetbeatz-release-bundle` | **the `.aab` that goes to Play** (~1.0 MB) — built and ZIP-verified on every push, so the publish run is never the first time it is compiled |
| `lint-report` | Android Lint findings, HTML |

### On your own machine — Android Studio

```bash
cd android
./gradlew assembleDebug            # → app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug             # with a device attached over USB
```

Requirements: **JDK 17** and the Android SDK with **platform 36** and **build-tools
36.0.0** (`sdkmanager "platforms;android-36" "build-tools;36.0.0"`). Android Studio
offers to install both when it opens the `android/` folder. Nothing else is needed —
there is no CocoaPods-style step and no generated code to fetch.

---

## 2. What the app adds to the website

| Behaviour | How |
| --- | --- |
| **Launcher icon, splash screen** | The MB monogram, cut from the same artwork the site uses, on the ink background. Generated by `tools/make_brand_assets.py`. |
| **Long-press shortcuts** | Beat store, Sound kits, Record online, Book studio time — each routed through android-browser-helper's validated trampoline, so only meetbeatz.com URLs can ever be opened. |
| **Deep links** | Tapping a meetbeatz.com link anywhere in Android opens the app. Requires `assetlinks.json` — see §3. |
| **Downloads** | Purchased MP3/WAV/stems and sound kits go to Android's `DownloadManager`: real progress in the notification shade, and they survive the app closing. The session cookie is copied onto the request, because `DownloadManager` runs outside the WebView. |
| **Microphone and camera** | `/record`, `/live-recording` and `/call` use `getUserMedia`. The WebView fallback grants those only after Android's own runtime permission is held. |
| **File uploads** | Artwork for `/distribution`, admin uploads and chat audio all use the system picker. |
| **Notifications** | Chrome delivers the site's notifications as Meetbeatz (delegated notifications), so they survive the tab being closed and tapping one reopens the app. |
| **Offline** | A branded offline page, cached by the service worker the site ships (see `web/`). |
| **Back button, payments, phone links** | Back navigates the page history, `tel:`/`mailto:`/WhatsApp links open their own app, and Paystack's popup plus 3-D Secure stay inside the app so the customer's session is never stranded in another browser. |

The app deliberately does **not** add a bottom navigation bar, a native beat list or a
second cart. The site already has all of that, and two of everything is how the prices on
the app and the prices on the site start disagreeing.

---

## 3. Verify the domain (removes the address bar)

Android only believes the app owns `meetbeatz.com` if the app's signing certificate is
listed at `https://meetbeatz.com/.well-known/assetlinks.json`.

```bash
# 1. Get the fingerprint of the key you sign releases with.
keytool -list -v -keystore android/meetbeatz-release.jks -alias meetbeatz | grep SHA256

# 2. Write it into the file the website serves, and keep the old ones (--append).
python3 tools/make_assetlinks.py \
    --fingerprint AA:BB:CC:… --append \
    --out web/public/.well-known/assetlinks.json

# 3. Deploy the website, then check on the device.
adb shell pm get-app-links com.meetbeatz.app
```

`tools/apply_web_patch.sh --fingerprint AA:BB:…` does steps 1–2 and opens the website pull
request in one go.

**Before verification the app still works fully** — it just shows the browser's address
bar on top, which is the classic "is this a real app?" giveaway. The fingerprint shipped
in `web/public/.well-known/assetlinks.json` is a **placeholder** and must be replaced.

---

## 4. Signing a release

### Create the key (once, and keep it)

```bash
keytool -genkeypair -v \
  -keystore android/meetbeatz-release.jks \
  -alias meetbeatz \
  -keyalg RSA -keysize 4096 -validity 10000 \
  -storetype JKS
```

Back this file up somewhere that is not this repository. If it is lost, existing installs
cannot be updated — they can only be replaced by a brand new listing.

### Point the build at it

Either locally, in `android/keystore.properties` (git-ignored):

```properties
storeFile=meetbeatz-release.jks
storePassword=…
keyAlias=meetbeatz
keyPassword=…
```

…or in CI, as repository secrets — four of them:

| Secret | Value |
| --- | --- |
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 android/meetbeatz-release.jks` |
| `ANDROID_KEYSTORE_PASSWORD` | the store password |
| `ANDROID_KEY_ALIAS` | `meetbeatz` |
| `ANDROID_KEY_PASSWORD` | the key password |

With those set, the Actions workflow signs the release build; without them it still
builds it, unsigned, so a broken release build is caught on the push that caused it.

### For Play, upload an AAB

```bash
cd android
./gradlew bundleRelease        # → app/build/outputs/bundle/release/app-release.aab
```

Play then **re-signs** the app with its own App Signing key, so the fingerprint to list
in `assetlinks.json` is the one from *Play Console → Test and release → App integrity →
App signing key certificate*, **not** the upload key's. Listing both is normal.

---

## 5. Publishing to Google Play

The upload itself is automated: **Actions → Publish to Google Play → Run workflow**.
Before that will work, three things have to exist — a Play account, the app in Play
Console, and two sets of secrets. Only you can do those, because Google requires the
account owner to verify their identity and sign in.

> **The button only appears after a merge.** GitHub shows *Run workflow* for a
> `workflow_dispatch` file only once that file is on the default branch, so until PR #1
> is merged into `main` the Actions tab will not offer it — that is not a sign anything
> is broken. The same job runs from a tag with no such restriction, and a `v*` tag is
> the route that works today:
>
> ```bash
> git tag v1.0.0 && git push origin v1.0.0
> ```
>
> Both routes run the identical workflow. The tag route uses the defaults — the
> `internalsharing` track, status `completed` — which is what you want anyway. It also
> produces the installable build described in §1, so `git tag v1.0.0 && git push origin
> v1.0.0` is the one command for a version: testers get a link, and Play gets the bundle.
>
> Before the upload key exists, the tag does both halves *without* failing: the release is
> published, and the Play job reports that it skipped itself. Only pressing the **Run
> workflow** button with no key configured is treated as an error, because then you clearly
> meant to publish.

### What I cannot do for you

Google gates all of this behind the account owner: creating the developer account
($25, identity verification), creating the app entry, and completing the store listing,
content-rating and data-safety forms. There is no API for account creation, and nobody
should be asking you for your Play password. Everything *after* that point is scripted.

### One-time setup

**1. The upload key** — on your own machine:

```bash
tools/make_upload_key.sh          # writes ~/meetbeatz-upload.jks and prints the secrets
```

Copy the four `ANDROID_KEYSTORE_*` values it prints into
**Settings → Secrets and variables → Actions**. Back the `.jks` file up somewhere that
is not this repository — lose it and you cannot update installed apps.

**2. The app in Play Console** — Play has no API for creating an app, so do it by hand:

1. Play Console → **Create app**. Name `Meetbeatz`, package name
   **`com.meetbeatz.app`**, app (not game), free.
2. **App integrity** → accept Play App Signing (the default). This is what re-signs
   every release.
3. Copy the **App signing key certificate → SHA-256** and put it in
   `web/public/.well-known/assetlinks.json` — this one, not the upload key's:

   ```bash
   python3 tools/make_assetlinks.py --fingerprint <play-signing-sha256> --append
   ```

**3. The service account** — how CI authenticates to Play without a password:

1. Google Cloud Console → the same project as your Play account → **IAM & Admin →
   Service accounts → Create**. No roles are needed here.
2. Open it → **Keys → Add key → JSON**. Download it.
3. Play Console → **Users and permissions → Invite new users** → paste the service
   account's email (`…@….iam.gserviceaccount.com`) → **App permissions**: grant it the
   app, with *Release to testing tracks* and (when you are ready) *Release to
   production*. Save.
4. Add the whole JSON file as the **`PLAY_SERVICE_ACCOUNT_JSON`** secret in GitHub.

That is the last of the sign-ins. Everything below is a button.

### Publishing

**Actions → Publish to Google Play → Run workflow**, then choose a track:

| Track | What it means |
| --- | --- |
| **`internalsharing`** *(default)* | No review, no listing, no testers. The run prints a **URL that installs the app on any signed-in device** within minutes. This is the fastest way to hold the real Play-signed build. |
| `internal` | Up to 100 testers you add by email. Needs the listing to exist. |
| `alpha` / `beta` | Closed and open testing. |
| `production` | Public. Submitted for review; new personal accounts must first run a closed test with 12+ testers for 14 days. |

Set **status** to `draft` to upload without submitting for review, and **dry_run** to
build and sign the bundle without uploading at all (useful for checking the build, or
for uploading the artifact by hand).

The run produces:

- `meetbeatz-aab` — the signed bundle, plus `mapping.txt` so Play can de-obfuscate
  crash reports (the release build is minified).
- A run summary with the track, the version and — on internal sharing — the install link.

It also verifies the bundle is signed before uploading, because Play's rejection for an
unsigned bundle arrives after the fact and reads like a Play problem rather than a
secret problem.

### Before each release

```bash
tools/bump_version_code.sh --name 1.1.0     # Play refuses a versionCode it has seen
```

Play rejects a bundle whose `versionCode` was already used, and the error surfaces after
the upload. Run this, commit, then run the workflow. After a release is live:

```bash
git tag v1.1.0 && git push origin v1.1.0    # tags also trigger the publish workflow
```

### The parts Play still needs from you, by hand

These are Console forms, not uploads — the workflow cannot fill them in:

1. **Privacy policy URL** — `https://meetbeatz.com/privacy` already exists.
2. **Data safety** — the app itself collects nothing; the website collects account and
   order details. The answers to copy are in [`play/store-listing.md`](play/store-listing.md).
3. **Content rating questionnaire** — music/store app, no public user-generated content.
   Five minutes, and it is required before any track other than internal sharing.
4. **Screenshots** — at least 2 phone screenshots; take them from the app itself so the
   splash screen and the store both show. The list is in the store-listing doc.
5. **App access** — if any part of the storefront needs a login, give review a test
   account so the release is not bounced.
6. **Store listing text, icon and feature graphic** — all written and generated; copy
   them from [`play/store-listing.md`](play/store-listing.md) and
   [`play/`](play/).

Only the release *notes* are automated: `docs/play/release-notes/whatsnew-en-US.txt` is
uploaded with every release. Edit that file and the change is what testers and customers
read under "What's new".

### Renaming the package (only before the first release)

This build uses **`com.meetbeatz.app`**. Changing it before the first Play release is a
five-minute find/replace; afterwards it is impossible, because Play ties an app's
identity, its signing key and every existing install to the package name.

```bash
grep -rl "com\.meetbeatz\.app" android/ web/ docs/ | xargs sed -i 's/com\.meetbeatz\.app/<new.id>/g'
```

The four places that actually matter are `applicationId`/`namespace` in
`android/app/build.gradle.kts`, the Kotlin `package` declaration (whose folder should be
renamed to match), `android:targetPackage` in `android/app/src/main/res/xml/shortcuts.xml`,
and `package_name` in `web/public/.well-known/assetlinks.json`. `python3 tools/ci_check.py`
then tells you whether they still agree — it cross-checks all four on every run.

---

## 6. When something looks wrong

| Symptom | Cause and fix |
| --- | --- |
| The app opens with a browser address bar on top | The domain is not verified. §3. Check `adb shell pm get-app-links com.meetbeatz.app`, and that `assetlinks.json` answers 200 over HTTPS with the right fingerprint. |
| "Open in browser" appears instead of the app | The TWA provider was not found. The app falls back to its WebView shell; a device with Chrome installed and enabled never does. |
| The store loads but the splash screen is missing | `res/drawable-nodpi/splash.png` is missing or was not regenerated — run `python3 tools/make_brand_assets.py`. |
| A paid file does not download | On Android 9 and below the app asks for storage permission when a download starts; refuse it and the file goes to the app's own folder instead, with a toast saying so. Also check the download link is a `GET` that the site authorises by session cookie. |
| Microphone is silent in `/record` | Android's microphone permission was denied. Long-press the app icon → App info → Permissions → Microphone. |
| The colour adjuster's export does nothing | That file is generated in the page (a `blob:` URL), which only a full browser can save. The app says so rather than failing silently, and offers to open the site in the browser — this is the one feature a WebView cannot complete. |
| Notifications never arrive | They are delegated to Chrome, so Chrome must be installed and the app's notification permission granted (Android 13+). Sending also needs the last piece on the website — see `web/README-ANDROID.md`, step 2. |
| A blank white page in the fallback shell | It means no browser on the device can host a TWA *and* the site failed to load. The offline screen appears with a **Try again** button; if it persists, check `chrome://inspect` on a USB-connected device (debug builds enable WebView debugging). |

---

## 7. Updating the app

The website changes without the app: prices, beats, pages and features are all server
side, so a typo fix on the site is live in the app the moment it is deployed. Cut a new
APK only when something in `android/` changes — an icon, the manifest, the fallback
shell, or a new Android version to target.

When you do:

1. Bump `versionCode` (must increase) and `versionName` in `android/app/build.gradle.kts`.
2. Push. Actions builds the APKs.
3. Upload the AAB under **Production → Create new release** in Play Console.

The app also asks Chrome to update its cached splash and theme from the manifest on each
launch, so a theme change on the site reaches installed apps without a new APK.

---

## Why a TWA

- **One product.** The site already has the store, the cart, Paystack, licensing, the
  audio player, the recording booth and the producer's admin. Rebuilding half of it
  natively would mean two places where a price can be wrong.
- **The browser engine you already trust.** Checkout happens in the same engine that
  passes Chrome's security updates, not in a WebView pinned to whatever shipped with the
  phone.
- **Small and fast.** The APK is a few hundred kilobytes; there is no second copy of the
  catalogue to install or keep in sync.
- **The Play Store accepts it.** Google's own guidance endorses TWAs for exactly this
  case: a site that is already a good mobile experience. To be explicit about the review
  risk: Play rejects *webviews without added value* and *broken web wrappers* — this is
  neither. It also rejects a TWA whose domain is not verified, which is why §3 is not
  optional before submitting.

What a TWA does **not** give you: a native UI shell, offline-first browsing of paid files
(they are downloads), or background audio that survives the screen locking. Those would
each mean a real native rewrite, and they are the honest answers for v2 — see the
[roadmap](#8-if-you-want-more) below.

---

## 8. If you want more

In rough order of value for a beat store:

1. **Push notifications** (~1 hour) — a booking alert on the producer's phone, "your
   licence is ready" on a customer's. The handlers, the subscription route and the
   database columns are already in the site patch; what remains is a sender in
   `notifyProducer()`. `web/README-ANDROID.md` step 2 has the reference implementation.
2. **Play Store listing** (§5) — the difference between a shared APK and something
   customers can find and update.
3. **A native mini-player** — replacing the site's player bar with a real Android media
   notification and lock-screen controls. This is the one feature that genuinely needs
   native code, and it needs an API on the website to feed it (now-playing JSON plus
   short-lived preview URLs), so it is a joint change.
4. **Saved beats** — a heart on each card that keeps a shortlist on the device, so a
   customer can come back for the beat they wanted.
5. **A beat-request inbox** — the site has `/contact`; a native form would let a rapper
   send "I need something like this, 110 BPM" in one tap from the store.

---

## What has and has not been verified

Being explicit, because most of this was written without an Android SDK in reach:

- **It compiles.** The Actions run builds `assembleDebug` and `assembleRelease` — Kotlin
  compilation, manifest merge, resource linking and R8 minification included — and
  publishes both APKs. `lintDebug` runs cleanly as its own job.
- **Verified here:** every resource reference resolves (`tools/ci_check.py`), no style
  implies a parent that does not exist, the manifest's origin and package agree with
  `assetlinks.json` and Gradle, every icon density exists, both Kotlin files are
  structurally sound, and the website patch applies cleanly to the site's current `main`.
- **Verified against the library source:** every android-browser-helper API the app
  overrides — `LauncherActivity.getCustomTabsCallback()`, `getFallbackStrategy()`,
  `TwaLauncher.FallbackStrategy`, `NotificationPermissionRequestActivity`,
  `ShortcutTrampolineActivity`, the `DelegationService` declaration and every splash
  metadata key — was read from `android-browser-helper` **2.7.4**, the version pinned in
  `android/gradle/libs.versions.toml`.
- **Found by CI rather than by reading:** the first build failed the resource link because
  a style named `Meetbeatz.Fallback.Title` implied a parent style that did not exist. The
  names are flat now, and `tools/ci_check.py` grew the check that catches it — verified by
  reintroducing the original name and watching the checker fail.
- **Not verified on a device:** the splash screen, deep-link verification, downloads,
  microphone capture and notification delegation all need a real phone. §6 lists what to
  check for each, and the debug APK from Actions is signed with a stable key so those
  checks can be repeated across builds.
