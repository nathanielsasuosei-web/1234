#!/usr/bin/env bash
#
# Apply the Android/PWA change to the website repository and open a pull request.
#
# The app in this repository is a Trusted Web Activity, so it needs three things
# from meetbeatz.com that only the website repository can provide:
#
#   1. a web app manifest and icons, so the site is installable;
#   2. a service worker, so a dead spot shows a branded offline page;
#   3. /.well-known/assetlinks.json, so Android verifies the app owns the domain.
#
# The change is kept here as a patch (web/patches/) because this session cannot
# write to the website repository — run this script somewhere you are authenticated
# as its owner and it will do the whole round trip.
#
# Usage
# -----
#   tools/apply_web_patch.sh                 # apply, push a branch, open a PR
#   tools/apply_web_patch.sh --dry-run       # clone and apply, print the diff, stop
#   tools/apply_web_patch.sh --fingerprint AA:BB:...   # bake in a real signing cert
#   tools/apply_web_patch.sh --site /path/to/existing/clone
#
# Requires: git, gh (authenticated), and network access to github.com.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH="$ROOT/web/patches/0001-make-site-installable-and-app-ready.patch"
SITE_REPO="${SITE_REPO:-nathanielsasuosei-web/meetbeatz}"
BRANCH="${BRANCH:-arena/pwa-android-app}"
FINGERPRINT=""
DRY_RUN=0
SITE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=1; shift ;;
    --fingerprint) FINGERPRINT="${2:?--fingerprint needs a SHA-256 value}"; shift 2 ;;
    --site) SITE_DIR="${2:?--site needs a path}"; shift 2 ;;
    --branch) BRANCH="${2:?--branch needs a name}"; shift 2 ;;
    -h|--help) sed -n '2,30p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$PATCH" ]] || { echo "missing patch: $PATCH" >&2; exit 1; }

workdir=""
cleanup() { [[ -n "$workdir" && -d "$workdir" ]] && rm -rf "$workdir"; }
trap cleanup EXIT

if [[ -n "$SITE_DIR" ]]; then
  cd "$SITE_DIR"
  echo "Using existing checkout at $SITE_DIR"
else
  workdir="$(mktemp -d)"
  echo "Cloning $SITE_REPO…"
  git clone --quiet "https://github.com/$SITE_REPO.git" "$workdir/site"
  cd "$workdir/site"
fi

git checkout --quiet main
git pull --quiet --ff-only || true

if git rev-parse --verify --quiet "$BRANCH" >/dev/null; then
  git checkout --quiet "$BRANCH"
  echo "Branch $BRANCH already exists here; using it."
else
  git checkout --quiet -b "$BRANCH"
fi

echo "Applying the patch…"
git apply --index "$PATCH"

# Optional: replace the placeholder certificate fingerprint with the real one, so
# Android verifies the app on the first install instead of the second deploy.
if [[ -n "$FINGERPRINT" ]]; then
  if [[ ! "$FINGERPRINT" =~ ^([0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}$ ]]; then
    echo "not a SHA-256 fingerprint: $FINGERPRINT" >&2; exit 1
  fi
  python3 - "$FINGERPRINT" <<'PY'
import json, sys, pathlib
fingerprint = sys.argv[1].upper()
path = pathlib.Path("public/.well-known/assetlinks.json")
document = json.loads(path.read_text())
target = document[0]["target"]
existing = [f for f in target["sha256_cert_fingerprints"] if not f.startswith("14:6D:E9")]
target["sha256_cert_fingerprints"] = existing + [fingerprint]
path.write_text(json.dumps(document, indent=2) + "\n")
print(f"assetlinks.json now lists {len(target['sha256_cert_fingerprints'])} fingerprint(s)")
PY
  git add public/.well-known/assetlinks.json
fi

echo
git --no-pager diff --cached --stat
echo

if [[ "$DRY_RUN" == "1" ]]; then
  echo "--dry-run: stopping before commit/push/PR."
  git --no-pager diff --cached -- public/sw.js | head -40
  exit 0
fi

if git diff --cached --quiet; then
  echo "Nothing to commit — the site may already have this change."
  exit 0
fi

git -c user.name="${GIT_AUTHOR_NAME:-Meetbeatz}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-mrmeetbeeatz@gmail.com}" \
    commit --quiet -F "$ROOT/web/COMMIT_MESSAGE.txt"

echo "Pushing $BRANCH…"
git push --quiet -u origin "$BRANCH"

if command -v gh >/dev/null 2>&1; then
  echo "Opening the pull request…"
  gh pr create --repo "$SITE_REPO" --base main --head "$BRANCH" \
    --title "Make the site installable and app-ready (manifest, offline shell, push plumbing)" \
    --body-file "$ROOT/web/PR_BODY.md"
  echo
  echo "Done. Deploy the preview, then confirm these answer 200:"
  echo "  https://meetbeatz.com/manifest.webmanifest"
  echo "  https://meetbeatz.com/sw.js"
  echo "  https://meetbeatz.com/.well-known/assetlinks.json"
else
  echo "gh is not installed: branch pushed, open the pull request from the GitHub UI."
fi
