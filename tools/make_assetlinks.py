#!/usr/bin/env python3
"""Write the Android App Links verification file for meetbeatz.com.

Google verifies that the app and the site belong to the same owner by comparing the
signing certificate of the installed app against the fingerprints listed at
https://meetbeatz.com/.well-known/assetlinks.json. Until that file lists the right
fingerprint the app still works — links just open with the browser's address bar on
top, which is what makes an unverified Trusted Web Activity look "wrong".

Usage
-----
    # Debug keystore (what a sideloaded APK is signed with)
    python3 tools/make_assetlinks.py --print-only

    # Release keystore, writing the file the website serves
    python3 tools/make_assetlinks.py \
        --keystore android/meetbeatz-release.jks \
        --alias meetbeatz \
        --password '...' \
        --out web/public/.well-known/assetlinks.json

    # From Play: Play Console → Test and release → App integrity → App signing key
    # certificate → SHA-256, which is NOT the same as the upload key's fingerprint.
    python3 tools/make_assetlinks.py --fingerprint AA:BB:... --append

Both fingerprints are expected to be listed at the same time: the Play-signed build
is what customers install, and the local debug build is what gets tested. A file with
several fingerprints verifies all of them.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "web" / "public" / ".well-known" / "assetlinks.json"
DEFAULT_DEBUG_KEYSTORE = Path.home() / ".android" / "debug.keystore"
PACKAGE_NAME = "com.meetbeatz.app"

FINGERPRINT_PATTERN = re.compile(r"^([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}$")


def normalise(fingerprint: str) -> str:
    cleaned = fingerprint.strip().replace(" ", "").upper()
    if not FINGERPRINT_PATTERN.match(cleaned):
        raise SystemExit(f"not a SHA-256 certificate fingerprint: {fingerprint!r}")
    return cleaned


def read_json(path: Path, out_path: Path) -> dict | None:
    """Load the currently deployed file, if it is a usable assetlinks document."""
    source = path if path.exists() else out_path
    if not source.exists():
        return None
    try:
        document = json.loads(source.read_text())
    except json.JSONDecodeError:
        print(f"  (ignoring unreadable {source})", file=sys.stderr)
        return None
    if isinstance(document, list) and document:
        return document[0]
    return None


def fingerprint_from_keytool(keystore: Path, alias: str | None, password: str | None) -> str:
    keytool = shutil.which("keytool")
    if keytool is None:
        raise SystemExit(
            "keytool was not found. It ships with the JDK — install one, or pass\n"
            "--fingerprint with the SHA-256 value from Play Console → App integrity."
        )
    if not keystore.exists():
        raise SystemExit(f"keystore not found: {keystore}")

    command = [
        keytool,
        "-list",
        "-v",
        "-keystore",
        str(keystore),
        "-storepass",
        password or "android",
        "-alias",
        alias or "androiddebugkey",
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(
            "keytool could not read the keystore:\n"
            f"{result.stdout.strip()}\n{result.stderr.strip()}"
        )

    match = re.search(r"SHA256:\s*([0-9A-Fa-f:]{95})", result.stdout)
    if not match:
        raise SystemExit("no SHA256 line in keytool output — is the alias correct?")
    return normalise(match.group(1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--keystore", type=Path, help="keystore holding the signing key")
    parser.add_argument("--alias", help="key alias inside the keystore")
    parser.add_argument("--password", help="keystore password (or storepass)")
    parser.add_argument(
        "--fingerprint",
        action="append",
        default=[],
        help="a SHA-256 fingerprint to include; repeat for more than one",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help=f"where to write (default: {DEFAULT_OUT})")
    parser.add_argument("--append", action="store_true", help="keep existing fingerprints and add to them")
    parser.add_argument("--print-only", action="store_true", help="show the document without writing it")
    args = parser.parse_args()

    keystore = args.keystore or (DEFAULT_DEBUG_KEYSTORE if DEFAULT_DEBUG_KEYSTORE.exists() else None)

    fingerprints: list[str] = [normalise(value) for value in args.fingerprint]
    if keystore is not None and args.keystore is not None:
        fingerprints.append(fingerprint_from_keytool(keystore, args.alias, args.password))
    elif not fingerprints and keystore is not None:
        # No arguments at all: fall back to the local debug keystore, which is what
        # `./gradlew assembleDebug` signs with.
        fingerprints.append(fingerprint_from_keytool(keystore, None, None))

    if not fingerprints:
        raise SystemExit("nothing to write: pass --keystore or --fingerprint")

    existing = read_json(args.out, args.out) if args.append else None
    if existing:
        carried = existing.get("target", {}).get("sha256_cert_fingerprints", [])
        fingerprints = [f for f in carried if f not in fingerprints] + fingerprints

    document = [
        {
            "relation": ["delegate_permission/common.handle_all_urls"],
            "target": {
                "namespace": "android_app",
                "package_name": PACKAGE_NAME,
                "sha256_cert_fingerprints": fingerprints,
            },
        }
    ]

    rendered = json.dumps(document, indent=2) + "\n"
    if args.print_only:
        print(rendered)
        return

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rendered)
    print(f"wrote {args.out}")
    print("Deploy it, then confirm with:")
    print(f"  curl -s https://meetbeatz.com/.well-known/assetlinks.json")
    print("and check Android's verification state with:")
    print("  adb shell pm get-app-links com.meetbeatz.app")


if __name__ == "__main__":
    main()
