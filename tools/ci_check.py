#!/usr/bin/env python3
"""Static checks for the Android app.

The app is a thin shell around a remote website, so almost nothing about it can be
tested here — the interesting behaviour happens in Chrome and on a phone. What *can*
be checked without a JDK, an SDK or a device is exactly the class of mistake that
otherwise only shows up as a red build or a blank screen at runtime:

  * a manifest that points at the wrong origin, or at a resource that is not there;
  * an `R.string.*` / `R.color.*` reference that does not resolve;
  * a launcher icon density that was never generated;
  * an App Links file whose package name or host disagrees with the manifest;
  * a Kotlin file with unbalanced braces.

`tools/ci_check.py` runs on every push (see .github/workflows/android.yml) and can be
run locally with plain Python 3 — no Gradle, no Android Studio.

Exit code 0 means every check passed; 1 means at least one failed and the message says
which file to open.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ANDROID = ROOT / "android"
APP = ANDROID / "app" / "src" / "main"
MANIFEST = APP / "AndroidManifest.xml"
RES = APP / "res"
KOTLIN = APP / "kotlin"
STRINGS = RES / "values" / "strings.xml"
ASSETLINKS = ROOT / "web" / "public" / ".well-known" / "assetlinks.json"
GRADLE = ANDROID / "app" / "build.gradle.kts"

EXPECTED_ORIGIN = "https://meetbeatz.com"
EXPECTED_HOST = "meetbeatz.com"
EXPECTED_PACKAGE = "com.meetbeatz.app"

DENSITIES = ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]

failures: list[str] = []
notes: list[str] = []


def fail(message: str) -> None:
    failures.append(message)


def ok(message: str) -> None:
    notes.append(message)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
        return ""
    return path.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- manifest


def check_manifest() -> str:
    manifest = read(MANIFEST)
    if not manifest:
        return ""

    default_url = re.search(
        r'android:name="android\.support\.customtabs\.trusted\.DEFAULT_URL"\s+android:value="([^"]+)"',
        manifest,
    )
    if not default_url:
        fail("AndroidManifest.xml: the launcher activity has no DEFAULT_URL metadata")
    elif "@string/" in default_url.group(1):
        site_url = re.search(r'<string name="site_url"[^>]*>([^<]+)</string>', read(STRINGS))
        resolved = site_url.group(1) if site_url else ""
        if resolved != EXPECTED_ORIGIN:
            fail(f'strings.xml: site_url is "{resolved}", expected "{EXPECTED_ORIGIN}"')
        else:
            ok(f"site_url is {EXPECTED_ORIGIN}")
    elif default_url.group(1).rstrip("/") != EXPECTED_ORIGIN:
        fail(f'DEFAULT_URL is "{default_url.group(1)}", expected "{EXPECTED_ORIGIN}"')

    for host in re.findall(r'<data[^>]*android:host="([^"]+)"', manifest):
        if host != EXPECTED_HOST:
            fail(f'AndroidManifest.xml declares the app link host "{host}"')

    for scheme in re.findall(r'<data[^>]*android:scheme="([^"]+)"', manifest):
        if scheme != "https":
            fail(f'AndroidManifest.xml declares the app link scheme "{scheme}"')

    if "android:autoVerify=" not in manifest:
        fail("AndroidManifest.xml: the app link intent filter is not autoVerify")

    for required in [
        "com.google.androidbrowserhelper.trusted.FocusActivity",
        "com.google.androidbrowserhelper.trusted.DelegationService",
        "com.google.androidbrowserhelper.trusted.NotificationPermissionRequestActivity",
        "com.google.androidbrowserhelper.trusted.ManageDataLauncherActivity",
        "androidx.core.content.FileProvider",
        ".MeetbeatzLauncherActivity",
        ".MeetbeatzWebViewActivity",
    ]:
        if required not in manifest:
            fail(f"AndroidManifest.xml is missing {required}")

    if 'android:name=".MeetbeatzWebViewActivity"' in manifest:
        block = manifest.split('android:name=".MeetbeatzWebViewActivity"', 1)[1].split(">", 1)[0]
        if 'android:exported="true"' in block:
            fail("MeetbeatzWebViewActivity must not be exported")

    return manifest


# ------------------------------------------------------------------ resource references


def defined_resources() -> dict[str, set[str]]:
    """Every resource name the Android build would define, keyed by type."""
    defined: dict[str, set[str]] = {
        "string": set(),
        "color": set(),
        "style": set(),
        "dimen": set(),
        "bool": set(),
        "integer": set(),
        "drawable": set(),
        "mipmap": set(),
        "xml": set(),
        "layout": set(),
    }

    for values_file in sorted((RES / "values").glob("*.xml")) + sorted(
        (RES / "values-night").glob("*.xml") if (RES / "values-night").exists() else []
    ):
        text = values_file.read_text(encoding="utf-8")
        for kind in ("string", "color", "dimen", "bool", "integer"):
            for name in re.findall(rf"<{kind}\s+name=\"([^\"]+)\"", text):
                defined[kind].add(name)
        for name in re.findall(r"<style\s+name=\"([^\"]+)\"", text):
            # Resource ids use underscores where the XML style name uses dots.
            defined["style"].add(name.replace(".", "_"))

    # File-based resources: the id is the file name without its qualifier or extension.
    for folder in RES.iterdir():
        if not folder.is_dir():
            continue
        kind = folder.name.split("-")[0]
        if kind not in defined:
            continue
        for item in sorted(folder.iterdir()):
            if item.suffix in {".png", ".webp", ".jpg", ".xml"} and ".9" not in item.name:
                defined[kind].add(item.stem)

    return defined


def check_resource_references(manifest: str, defined: dict[str, set[str]]) -> None:
    text = manifest + "\n".join(
        path.read_text(encoding="utf-8") for path in sorted(RES.rglob("*.xml"))
    )

    for kind, name in re.findall(r"@(?:\+)?(string|color|drawable|mipmap|style|xml)/([A-Za-z0-9_.]+)", text):
        if kind == "style":
            name = name.replace(".", "_")
        if name not in defined[kind]:
            fail(f"unresolved resource reference: @{kind}/{name}")

    for kotlin in sorted(KOTLIN.rglob("*.kt")):
        source = kotlin.read_text(encoding="utf-8")
        for kind, name in re.findall(r"\bR\.(string|color|drawable|mipmap|style|xml|layout)\.([A-Za-z0-9_.]+)", source):
            if name not in defined[kind]:
                fail(f"{kotlin.name}: unresolved R.{kind}.{name}")

    ok(f"{len(defined['string'])} strings, {len(defined['color'])} colours and "
       f"{len(defined['style'])} styles all resolve")


# ------------------------------------------------------------------------- brand assets


def check_assets() -> None:
    splash = RES / "drawable-nodpi" / "splash.png"
    if not splash.exists():
        fail("missing the splash image: res/drawable-nodpi/splash.png")

    for density in DENSITIES:
        folder = RES / f"mipmap-{density}"
        for name in ("ic_launcher.png", "ic_launcher_round.png", "ic_launcher_foreground.png", "ic_launcher_monochrome.png"):
            if not (folder / name).exists():
                fail(f"missing launcher icon: mipmap-{density}/{name}")

    for name in ("ic_launcher.xml", "ic_launcher_round.xml"):
        if not (RES / "mipmap-anydpi-v26" / name).exists():
            fail(f"missing adaptive icon: mipmap-anydpi-v26/{name}")

    for name in ("shortcuts.xml", "filepaths.xml", "backup_rules.xml", "data_extraction_rules.xml"):
        if not (RES / "xml" / name).exists():
            fail(f"missing res/xml/{name}")

    for icon in ("ic_shortcut_store", "ic_shortcut_kits", "ic_shortcut_record", "ic_shortcut_studio"):
        if not (RES / "drawable" / f"{icon}.xml").exists():
            fail(f"missing shortcut icon: res/drawable/{icon}.xml")

    web_icons = ROOT / "web" / "public" / "icons"
    for name in ("icon-192.png", "icon-512.png", "maskable-512.png", "apple-touch-icon.png"):
        if not (web_icons / name).exists():
            fail(f"missing web app icon: web/public/icons/{name}")


def check_shortcuts() -> None:
    shortcuts = read(RES / "xml" / "shortcuts.xml")
    if not shortcuts:
        return
    targets = set(re.findall(r'android:targetClass="([^"]+)"', shortcuts))
    if targets != {"com.google.androidbrowserhelper.trusted.ShortcutTrampolineActivity"}:
        fail("res/xml/shortcuts.xml must target ShortcutTrampolineActivity, not the launcher")
    for url in re.findall(r'android:data="([^"]+)"', shortcuts):
        if not url.startswith(EXPECTED_ORIGIN):
            fail(f"res/xml/shortcuts.xml points outside the site: {url}")


# ----------------------------------------------------------------- asset links & Gradle


def check_asset_links() -> None:
    if not ASSETLINKS.exists():
        note = "web/public/.well-known/assetlinks.json is not present"
        notes.append(note)
        return

    try:
        document = json.loads(ASSETLINKS.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        fail(f"assetlinks.json is not valid JSON: {error}")
        return

    if not isinstance(document, list) or not document:
        fail("assetlinks.json must be a non-empty array")
        return

    target = document[0].get("target", {})
    if target.get("package_name") != EXPECTED_PACKAGE:
        fail(
            f'assetlinks.json names the package "{target.get("package_name")}", '
            f"but the app's applicationId is {EXPECTED_PACKAGE}"
        )

    fingerprints = target.get("sha256_cert_fingerprints", [])
    if not fingerprints:
        fail("assetlinks.json lists no sha256_cert_fingerprints")
    else:
        placeholder = "14:6D:E9:83:C5:73:06:50:D8:EE:B9:95:2F:34:FC:64:16:A0:83:42:E6:1D:BE:A8:8A:04:96:B2:3F:CF:44:E5"
        if fingerprints == [placeholder]:
            notes.append(
                "assetlinks.json still carries the placeholder fingerprint — the app works, "
                "but links open with the browser bar until tools/make_assetlinks.py writes the real one"
            )


def check_gradle() -> None:
    gradle = read(GRADLE)
    if not gradle:
        return

    application_id = re.search(r'applicationId\s*=\s*"([^"]+)"', gradle)
    if not application_id:
        fail("app/build.gradle.kts has no applicationId")
    elif application_id.group(1) != EXPECTED_PACKAGE:
        fail(f'applicationId is "{application_id.group(1)}", expected {EXPECTED_PACKAGE}')

    if not re.search(r"versionCode\s*=\s*\d+", gradle):
        fail("app/build.gradle.kts has no versionCode")
    if not re.search(r'versionName\s*=\s*"', gradle):
        fail("app/build.gradle.kts has no versionName")

    for dependency in ("android.browser.helper", "androidx.browser", "androidx.core.ktx"):
        if dependency not in gradle:
            fail(f"app/build.gradle.kts no longer depends on {dependency}")

    if not (ANDROID / "gradle" / "wrapper" / "gradle-wrapper.jar").exists():
        fail("the Gradle wrapper jar is missing — `./gradlew` cannot run")

    if not (ROOT / ".github" / "workflows" / "android.yml").exists():
        fail(".github/workflows/android.yml is missing, so no APK is built")


# --------------------------------------------------------------------------- Kotlin


def check_kotlin_balance() -> None:
    """A crude brace/paren balance check that ignores strings and comments.

    Not a compiler — just a tripwire for a truncated or hand-edited file, which is
    otherwise only discovered by a red build several minutes later.
    """
    pairs = {"{": "}", "(": ")", "[": "]"}
    closing = {value: key for key, value in pairs.items()}
    checked = 0

    for path in sorted(KOTLIN.rglob("*.kt")):
        checked += 1
        source = path.read_text(encoding="utf-8")
        stack: list[str] = []
        index = 0
        state = "code"
        while index < len(source):
            char = source[index]
            nxt = source[index + 1] if index + 1 < len(source) else ""

            if state == "code":
                if char == "/" and nxt == "/":
                    state = "line_comment"
                    index += 1
                elif char == "/" and nxt == "*":
                    state = "block_comment"
                    index += 1
                elif char == '"' and source[index : index + 3] == '"""':
                    state = "raw_string"
                    index += 2
                elif char == '"':
                    state = "string"
                elif char == "'":
                    state = "char"
                elif char in pairs:
                    stack.append(char)
                elif char in closing:
                    if not stack or stack.pop() != closing[char]:
                        fail(f"{path.name}: unbalanced '{char}'")
                        break
            elif state == "line_comment":
                if char == "\n":
                    state = "code"
            elif state == "block_comment":
                if char == "*" and nxt == "/":
                    state = "code"
                    index += 1
            elif state == "string":
                if char == "\\":
                    index += 1
                elif char == "\n":
                    state = "code"
                elif char == '"':
                    state = "code"
            elif state == "char":
                if char == "\\":
                    index += 1
                elif char == "'":
                    state = "code"
            elif state == "raw_string":
                if char == '"' and source[index : index + 3] == '"""':
                    state = "code"
                    index += 2
            index += 1

        if stack:
            fail(f"{path.name}: {len(stack)} unclosed {stack[-1]}")

    if checked == 0:
        fail("no Kotlin sources found under app/src/main/kotlin")
    else:
        ok(f"{checked} Kotlin sources balanced")


# ----------------------------------------------------------------------------- main


def main() -> int:
    defined = defined_resources()
    manifest = check_manifest()
    check_resource_references(manifest, defined)
    check_assets()
    check_shortcuts()
    check_asset_links()
    check_gradle()
    check_kotlin_balance()

    for note in notes:
        print(f"  · {note}")

    if failures:
        print(f"\n{len(failures)} problem(s):")
        for failure in failures:
            print(f"  ✗ {failure}")
        return 1

    print("\nAll static checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
