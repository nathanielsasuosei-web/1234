#!/usr/bin/env bash
#
# Prove the website patch is safe to deploy, before it is.
#
# Applies web/patches/0001-*.patch to a clean checkout of the website repository and
# runs that project's own gates against the result:
#
#   npm install      the site's dependencies
#   tsc --noEmit     the type check `next build` performs
#   npm run build    the real production build, including the project's own
#                    check-tracked-sources and check-upload-routes guards
#
# Why it exists: the first version of this patch shipped an API route importing two
# helpers the site does not export, and writing a column the schema did not have. Both
# are type errors, both would have failed `npm run build` on the deploy — and nothing in
# the Android build could notice, because the app only talks to the deployed site over
# HTTP. This script is the missing gate. `python3 tools/ci_check.py` carries a cheap
# static version of the same check for CI; this one is the thorough version for a human.
#
# Usage
# -----
#   tools/verify_web_patch.sh                    # clone, apply, typecheck, build
#   tools/verify_web_patch.sh --site /path       # reuse an existing checkout
#   tools/verify_web_patch.sh --typecheck-only   # skip the production build (~40 s)
#
# Requires: git, node 18+, npm, and network access to github.com and the npm registry.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH="$ROOT/web/patches/0001-make-site-installable-and-app-ready.patch"
SITE_REPO="${SITE_REPO:-nathanielsasuosei-web/meetbeatz}"
SITE_DIR=""
RUN_BUILD=1

while [[ $# -gt 0 ]]; do
  case "$1" in
    --site) SITE_DIR="${2:?--site needs a path}"; shift 2 ;;
    --typecheck-only) RUN_BUILD=0; shift ;;
    -h|--help) sed -n '2,26p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$PATCH" ]] || { echo "missing patch: $PATCH" >&2; exit 1; }
command -v node >/dev/null || { echo "node is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm is required" >&2; exit 1; }

workdir=""
cleanup() { [[ -n "$workdir" && -d "$workdir" ]] && rm -rf "$workdir"; }
trap cleanup EXIT

if [[ -n "$SITE_DIR" ]]; then
  cd "$SITE_DIR"
  had_node_modules=0
  [[ -d node_modules ]] && had_node_modules=1
else
  workdir="$(mktemp -d)"
  echo "Cloning $SITE_REPO…"
  git clone --quiet "https://github.com/$SITE_REPO.git" "$workdir/site"
  cd "$workdir/site"
  had_node_modules=0
fi

echo "Site checkout: $(git log --oneline -1)"

# The checkout must be pristine before the patch is applied, or the result means nothing.
if [[ -n "$(git status --porcelain -- . ':!node_modules' 2>/dev/null || git status --porcelain)" ]]; then
  echo "This checkout has local changes. Use a clean clone, or commit/stash them first." >&2
  git status --short | head -10 >&2
  exit 1
fi

echo "Applying the patch…"
git apply "$PATCH"
echo "  applied ✓"

if [[ "$had_node_modules" == "0" ]]; then
  echo "Installing dependencies (npm install)…"
  npm install --no-audit --no-fund --loglevel=error >/dev/null 2>&1 || {
    echo "npm install failed — run it by hand to see why:" >&2
    npm install --no-audit --no-fund >&2
    exit 1
  }
  echo "  installed ✓"
else
  echo "Reusing node_modules from the given checkout."
fi

echo "Type checking (tsc --noEmit)…"
if npx tsc --noEmit 2>&1 | tee "$PWD/.tsc.log" | head -30 | grep -q .; then
  # tsc printed diagnostics — the patch does not typecheck.
  echo
  echo "FAILED: the patched site does not type check. Errors above." >&2
  exit 1
fi
echo "  clean ✓"

if [[ "$RUN_BUILD" == "1" ]]; then
  echo "Production build (npm run build)…"
  echo "  (no DATABASE_URL is set on purpose: the schema sync reports a missing"
  echo "   connection as a warning, so the build is what a fresh deploy does first.)"
  if ! npm run build > "$PWD/.build.log" 2>&1; then
    echo "FAILED: the patched site does not build. Last 40 lines:" >&2
    tail -40 "$PWD/.build.log" >&2
    exit 1
  fi
  echo "  built ✓"
fi

echo
echo "The patch applies to $(git log --oneline -1) and passes the site's own gates."
