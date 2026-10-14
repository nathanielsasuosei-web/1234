#!/usr/bin/env bash
#
# Regenerate web/patches/0001-make-site-installable-and-app-ready.patch.
#
# The website change lives in this repository in two pieces:
#
#   web/public/**, web/src/**          new files, kept here as the editable copy
#   web/patches/layout-edit.patch       the one edit to an existing file
#
# and this script folds them into a single patch against the website repository's
# main branch. Run it after editing anything under web/, then either commit the
# regenerated patch or hand it to tools/apply_web_patch.sh.
#
# Usage
# -----
#   tools/make_web_patch.sh                     # clone the site, rebuild the patch
#   tools/make_web_patch.sh --site /path/clone  # use an existing checkout
#
# Requires: git, and network access to github.com.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_REPO="${SITE_REPO:-nathanielsasuosei-web/meetbeatz}"
OUT="$ROOT/web/patches/0001-make-site-installable-and-app-ready.patch"
LAYOUT_PATCH="$ROOT/web/patches/layout-edit.patch"
SITE_DIR=""
BRANCH="arena/pwa-android-app"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) SITE_DIR="${2:?--site needs a path}"; shift 2 ;;
    --out) OUT="${2:?--out needs a path}"; shift 2 ;;
    -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$LAYOUT_PATCH" ]] || { echo "missing $LAYOUT_PATCH" >&2; exit 1; }

workdir=""
cleanup() { [[ -n "$workdir" && -d "$workdir" ]] && rm -rf "$workdir"; }
trap cleanup EXIT

if [[ -n "$SITE_DIR" ]]; then
  cd "$SITE_DIR"
  git fetch --quiet origin main
else
  workdir="$(mktemp -d)"
  echo "Cloning $SITE_REPO…"
  git clone --quiet "https://github.com/$SITE_REPO.git" "$workdir/site"
  cd "$workdir/site"
fi

git checkout --quiet --detach origin/main 2>/dev/null || git checkout --quiet --detach main
BASE="$(git rev-parse HEAD)"
git checkout --quiet -B "$BRANCH"

echo "Copying web/ into the checkout…"
mkdir -p public/.well-known public/icons src/components src/app/api/push/subscribe
cp "$ROOT/web/public/manifest.webmanifest" public/manifest.webmanifest
cp "$ROOT/web/public/sw.js" public/sw.js
cp "$ROOT/web/public/offline.html" public/offline.html
cp "$ROOT"/web/public/icons/*.png public/icons/
cp "$ROOT/web/public/.well-known/assetlinks.json" public/.well-known/assetlinks.json
cp "$ROOT/web/src/components/service-worker-registrar.tsx" src/components/service-worker-registrar.tsx
cp "$ROOT/web/src/app/api/push/subscribe/route.ts" src/app/api/push/subscribe/route.ts

if git apply --check "$LAYOUT_PATCH" 2>/dev/null; then
  git apply "$LAYOUT_PATCH"
  echo "Applied the layout.tsx edit."
elif git apply --check --reverse "$LAYOUT_PATCH" 2>/dev/null; then
  echo "layout.tsx already carries the edit."
else
  echo "layout.tsx has drifted from the patch — resolve web/patches/layout-edit.patch by hand." >&2
  exit 1
fi

git add -A
if git diff --cached --quiet; then
  echo "Nothing changed: the website already matches web/." >&2
  exit 0
fi

git -c user.name="${GIT_AUTHOR_NAME:-Meetbeatz}" \
    -c user.email="${GIT_AUTHOR_EMAIL:-mrmeetbeeatz@gmail.com}" \
    commit --quiet -F "$ROOT/web/COMMIT_MESSAGE.txt"

echo "Writing $OUT"
git format-patch --binary --stdout "$BASE..HEAD" > "$OUT"

# Prove the artifact is usable before it is committed.
git checkout --quiet "$BASE"
if git apply --check "$OUT"; then
  echo "Verified: the patch applies cleanly to $(git rev-parse --short "$BASE") ($(git symbolic-ref -q --short HEAD || echo detached))."
else
  echo "the regenerated patch does NOT apply to its own base — not committing it" >&2
  exit 1
fi

echo
echo "Summary:"
git apply --stat "$OUT"
