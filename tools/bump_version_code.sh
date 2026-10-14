#!/usr/bin/env bash
#
# Raise versionCode (and optionally versionName) in android/app/build.gradle.kts.
#
# Play refuses a bundle whose versionCode has already been used for that app, and the
# rejection arrives after the upload — so this is the step to run before every release.
# It edits one line, prints the change, and reminds you about the tag.
#
# Usage
# -----
#   tools/bump_version_code.sh                     # 1 → 2, keeps versionName
#   tools/bump_version_code.sh --name 1.1.0        # 1.0.0 → 1.1.0, code 1 → 2
#   tools/bump_version_code.sh --to 25             # jump to an exact code (Play fallback)
#
# Requires: nothing but a POSIX shell.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GRADLE="$ROOT/android/app/build.gradle.kts"
NEW_NAME=""
EXACT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NEW_NAME="${2:?--name needs a version like 1.1.0}"; shift 2 ;;
    --to) EXACT="${2:?--to needs a number}"; shift 2 ;;
    -h|--help) sed -n '2,16p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$GRADLE" ]] || { echo "missing $GRADLE" >&2; exit 1; }

current_code="$(grep -oP 'versionCode\s*=\s*\K[0-9]+' "$GRADLE")"
current_name="$(grep -oP 'versionName\s*=\s*"\K[^"]+' "$GRADLE")"

if [[ -n "$EXACT" ]]; then
  [[ "$EXACT" =~ ^[0-9]+$ ]] || { echo "--to must be a number" >&2; exit 1; }
  new_code="$EXACT"
else
  new_code=$((current_code + 1))
fi

if (( new_code <= current_code )); then
  echo "Refusing to move the version code backwards ($current_code → $new_code)." >&2
  echo "Play only accepts a code higher than every code already uploaded for this app." >&2
  exit 1
fi

new_name="${NEW_NAME:-$current_name}"

python3 - "$GRADLE" "$current_code" "$new_code" "$current_name" "$new_name" <<'PY'
import re
import sys
from pathlib import Path

path, old_code, new_code, old_name, new_name = sys.argv[1:6]
text = Path(path).read_text()
before = text

text = re.sub(rf"(versionCode\s*=\s*){re.escape(old_code)}\b", rf"\g<1>{new_code}", text, count=1)
text = re.sub(rf'(versionName\s*=\s*"){re.escape(old_name)}(")', rf"\g<1>{new_name}\g<2>", text, count=1)

if text == before:
    raise SystemExit("nothing changed — is the version declared somewhere else?")

Path(path).write_text(text)
PY

echo "versionCode $current_code → $new_code"
[[ "$current_name" != "$new_name" ]] && echo "versionName $current_name → $new_name"

echo
echo "Next:"
echo "  1. Commit this change."
echo "  2. Push, or run Actions → Publish to Google Play → Run workflow."
echo "  3. After the release is live, tag it:  git tag v${new_name} && git push origin v${new_name}"
echo
echo "The Play upload also needs the upload key (tools/make_upload_key.sh) and the"
echo "service account secret — see docs/ANDROID_APP.md §5."
