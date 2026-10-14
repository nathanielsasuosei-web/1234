#!/usr/bin/env bash
#
# Create the Play upload key, and print exactly what to paste where.
#
# Run this ONCE, on your own machine. It generates the keystore Google Play signs
# uploads against and prints:
#
#   * the four values for the repository's ANDROID_KEYSTORE_* secrets
#   * the SHA-256 fingerprint of the certificate, for reference
#
# Two things worth understanding before you start, because they are the two mistakes
# that cost people their app:
#
#   1. **Back the keystore up somewhere that is not this repository.** If it is lost,
#      you cannot update an installed app — Google's key recovery exists but is a
#      support process, not a button.
#   2. **The fingerprint in assetlinks.json is NOT this one.** Play re-signs every
#      release with its own App Signing key, so the value that verifies deep links is
#      the one from Play Console → Test and release → App integrity. Listing both is
#      fine and normal; listing only this one is why apps show a browser address bar
#      after their first Play install.
#
# The keystore is written outside the repository by default, so it cannot be committed
# by accident. Paths inside the repository are refused unless you insist with --force.
#
# Usage
# -----
#   tools/make_upload_key.sh                          # ~/meetbeatz-upload.jks
#   tools/make_upload_key.sh --out /secure/path.jks   # somewhere else
#   tools/make_upload_key.sh --alias meetbeatz-mobile
#
# Requires: keytool (ships with any JDK), base64, and openssl or shasum for the
# fingerprint (optional — keytool prints it too).

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${HOME}/meetbeatz-upload.jks"
ALIAS="meetbeatz"
DAYS=10000
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out) OUT="${2:?--out needs a path}"; shift 2 ;;
    --alias) ALIAS="${2:?--alias needs a name}"; shift 2 ;;
    --days) DAYS="${2:?--days needs a number}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) sed -n '2,32p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

command -v keytool >/dev/null || {
  echo "keytool is not installed. It ships with the JDK — install a JDK 17, or run this" >&2
  echo "from Android Studio's bundled JDK." >&2
  exit 1
}

# Never write signing material into the repository.
case "$(cd "$(dirname "$OUT")" 2>/dev/null && pwd || echo "$OUT")" in
  "$ROOT"*)
    if [[ "$FORCE" != "1" ]]; then
      echo "Refusing to write a keystore inside the repository ($ROOT)." >&2
      echo "Pick a path outside it, or pass --force if you really mean it" >&2
      echo "(android/*.jks is git-ignored, but an ignored secret is still a secret on disk)." >&2
      exit 1
    fi
    ;;
esac

if [[ -e "$OUT" ]]; then
  echo "$OUT already exists — refusing to overwrite a signing key." >&2
  echo "Delete it yourself if you are certain, or choose another --out path." >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT")"

read -r -s -p "Choose a keystore password (you will need it again): " PASSWORD
echo
read -r -s -p "Repeat it: " PASSWORD_CONFIRM
echo
[[ "$PASSWORD" == "$PASSWORD_CONFIRM" ]] || { echo "Passwords do not match." >&2; exit 1; }
[[ ${#PASSWORD} -ge 8 ]] || { echo "Use at least 8 characters." >&2; exit 1; }

echo
echo "Generating a 4096-bit RSA key (valid until $(date -d "+${DAYS} days" +%Y) or so)…"
keytool -genkeypair -v \
  -keystore "$OUT" \
  -alias "$ALIAS" \
  -keyalg RSA -keysize 4096 -validity "$DAYS" \
  -storetype PKCS12 \
  -storepass "$PASSWORD" \
  -keypass "$PASSWORD" \
  -dname "CN=Meetbeatz, OU=Android, O=Meetbeatz, L=Accra, C=GH" \
  > /dev/null

FINGERPRINT="$(keytool -list -v -keystore "$OUT" -storepass "$PASSWORD" -alias "$ALIAS" \
  | grep -i "SHA256:" | head -1 | sed 's/.*SHA256: *//')"

BASE64_KEY="$(base64 -w0 "$OUT" 2>/dev/null || base64 "$OUT" | tr -d '\n')"

cat <<EOF

================================================================================
Upload key created: $OUT
Alias: $ALIAS
Certificate SHA-256 (the UPLOAD key, not the Play signing key):
  $FINGERPRINT
================================================================================

1. BACK IT UP NOW — somewhere that is not this repository: a password manager's
   file storage, an encrypted archive you keep offline, or both. Losing it means you
   cannot update an installed app.

2. Add these four secrets to the app repository:
   GitHub → Settings → Secrets and variables → Actions → New repository secret

   ANDROID_KEYSTORE_BASE64
$(printf '%s' "$BASE64_KEY" | fold -w 100 | sed 's/^/     /')

   ANDROID_KEYSTORE_PASSWORD
     (the password you just typed)

   ANDROID_KEY_ALIAS
     $ALIAS

   ANDROID_KEY_PASSWORD
     (the same password again — PKCS12 uses one password for both)

3. Add the fifth secret only once you have created the Play service account:
   PLAY_SERVICE_ACCOUNT_JSON   (the whole JSON file, pasted as-is)
   See docs/ANDROID_APP.md §5.

4. Then: Actions → Publish to Google Play → Run workflow.
   The default track is \`internalsharing\`, which installs on your phone in minutes
   with no review and no testers — the fastest way to see the real build.

Remember: the fingerprint that goes in .well-known/assetlinks.json is the one from
Play Console → Test and release → App integrity → App signing key certificate,
because Play re-signs your uploads. This upload key's fingerprint is not it.
EOF

# Never leave the base64 of a signing key lying around in a log people paste into chat.
unset BASE64_KEY PASSWORD PASSWORD_CONFIRM
