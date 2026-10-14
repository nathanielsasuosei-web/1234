#!/usr/bin/env bash
#
# Run the patched website locally, with a real database, and look at it.
#
# This is how the website change is previewed before it is deployed: it clones the
# site, applies web/patches/0001-*.patch, installs its dependencies, starts an
# embedded Postgres (PGlite — Postgres compiled to WebAssembly, so there is nothing to
# install or sign up for), creates the schema from the site's own drizzle definition,
# builds, and serves the result on a port you can open.
#
# What you see is what the Android app shows: the app is a Trusted Web Activity around
# this exact site. Opening the URL on an Android phone in Chrome and choosing
# "Install app" gives the standalone experience — new icon, splash screen, no browser
# UI — which is a good way to try an Android phone preview without installing an APK.
#
# Usage
# -----
#   tools/preview_web_patch.sh                     # http://localhost:3000
#   tools/preview_web_patch.sh --port 3010         # another port
#   tools/preview_web_patch.sh --refresh           # re-clone, re-apply, re-install
#   tools/preview_web_patch.sh --site /path        # reuse a checkout you already have
#
# Stop it with Ctrl-C; the embedded database is stopped with it.
#
# Requires: git, node 18+, npm, and network access to github.com and the npm registry.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PATCH="$ROOT/web/patches/0001-make-site-installable-and-app-ready.patch"
SITE_REPO="${SITE_REPO:-nathanielsasuosei-web/meetbeatz}"
WORKDIR="${ROOT}/.preview/site"
PORT="3000"
DB_PORT="55432"
SITE_DIR=""
REFRESH=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --port) PORT="${2:?--port needs a number}"; shift 2 ;;
    --db-port) DB_PORT="${2:?--db-port needs a number}"; shift 2 ;;
    --workdir) WORKDIR="${2:?--workdir needs a path}"; shift 2 ;;
    --site) SITE_DIR="${2:?--site needs a path}"; shift 2 ;;
    --refresh) REFRESH=1; shift ;;
    -h|--help) sed -n '2,24p' "${BASH_SOURCE[0]}"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$PATCH" ]] || { echo "missing patch: $PATCH" >&2; exit 1; }
command -v node >/dev/null || { echo "node is required" >&2; exit 1; }
command -v npm >/dev/null || { echo "npm is required" >&2; exit 1; }

export DATABASE_URL="postgresql://postgres:postgres@127.0.0.1:${DB_PORT}/postgres"
export SESSION_SECRET="preview-only-secret-not-for-production-32"
export ADMIN_EMAIL="preview@meetbeatz.com"
export ADMIN_PASSWORD="MeetbeatzPreview2026"
export PAYMENT_MODE="simulation"

# NODE_ENV is deliberately NOT exported here. `next build` and `next start` set it
# themselves, and exporting it before `npm install` makes npm treat the install as a
# production deploy — which silently skips every devDependency, including drizzle-kit
# and typescript, so the schema never syncs and the build fails with confusing
# "Can't resolve '@/db'" errors. (Learned the hard way; see the preflight below.)

db_pid=""
cleanup() {
  if [[ -n "$db_pid" ]] && kill -0 "$db_pid" 2>/dev/null; then
    kill "$db_pid" 2>/dev/null || true
    wait "$db_pid" 2>/dev/null || true
    echo
    echo "Embedded Postgres stopped."
  fi
}
trap cleanup EXIT INT TERM

# ------------------------------------------------------------------ get the site
if [[ -n "$SITE_DIR" ]]; then
  SITE="$SITE_DIR"
  echo "Using the checkout at $SITE"
else
  SITE="$WORKDIR"
  if [[ "$REFRESH" == "1" || ! -d "$SITE/.git" ]]; then
    echo "Cloning $SITE_REPO into $SITE…"
    rm -rf "$SITE"
    mkdir -p "$(dirname "$SITE")"
    git clone --quiet "https://github.com/$SITE_REPO.git" "$SITE"
  fi
  cd "$SITE"
  git fetch --quiet origin main || true
  git checkout --quiet --detach origin/main 2>/dev/null || git checkout --quiet main
fi
cd "$SITE"
echo "Site: $(git log --oneline -1)"

# ------------------------------------------------------------------ apply the patch
if git apply --check "$PATCH" 2>/dev/null; then
  git apply "$PATCH"
  echo "Patch applied."
elif git apply --check --reverse "$PATCH" 2>/dev/null; then
  echo "Patch already applied in this checkout."
else
  echo "The patch does not apply cleanly here — run tools/make_web_patch.sh first." >&2
  exit 1
fi

# ------------------------------------------------------------------- dependencies
if [[ "$REFRESH" == "1" || ! -d node_modules/next ]]; then
  echo "Installing the site's dependencies (this takes a minute the first time)…"
  npm install --include=dev --no-audit --no-fund --loglevel=error
fi

if [[ ! -d node_modules/@electric-sql/pglite ]]; then
  echo "Adding the embedded database (PGlite)…"
  npm install --include=dev --no-audit --no-fund --loglevel=error \
    @electric-sql/pglite @electric-sql/pglite-socket
fi

# Preflight: everything the next few steps call has to actually be here. Checked
# explicitly because the failure mode is otherwise a wall of unrelated errors.
for required in next drizzle-kit typescript; do
  if [[ ! -e "node_modules/$required" && ! -x "node_modules/.bin/$required" ]]; then
    echo "node_modules is missing '$required' — the install did not complete." >&2
    echo "Try: rm -rf node_modules package-lock.json && npm install --include=dev" >&2
    exit 1
  fi
done

# ---------------------------------------------------------------- embedded postgres
# A tiny wire-protocol server, so the site's ordinary `pg` connection string works
# without a Postgres install. Preview scaffolding: it lives in the ignored workdir.
cat > "$SITE/.preview-db-server.mjs" <<'JS'
import { PGlite } from "@electric-sql/pglite";
import { PGLiteSocketServer } from "@electric-sql/pglite-socket";

const [dataDir, port] = [process.argv[2], Number(process.argv[3])];
const db = await PGlite.create({ dataDir });
const server = new PGLiteSocketServer({ db, port, host: "127.0.0.1", maxConnections: 8 });
await server.start();
console.log(`embedded postgres on 127.0.0.1:${port}`);
for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, async () => { await server.stop(); await db.close(); process.exit(0); });
}
JS

echo "Starting the embedded database on port $DB_PORT…"
node "$SITE/.preview-db-server.mjs" "$SITE/.preview-db" "$DB_PORT" &
db_pid=$!

for _ in $(seq 1 40); do
  node -e "
  const { Client } = require('pg');
  const c = new Client({ connectionString: process.env.DATABASE_URL });
  c.connect().then(() => c.end()).then(() => process.exit(0)).catch(() => process.exit(1));
  " 2>/dev/null && break
  sleep 0.5
done
echo "Database ready."

echo "Creating the schema (the same step a deploy runs)…"
if ! node scripts/push-schema-on-build.mjs; then
  echo "Schema sync failed — the preview would have no tables, so stopping here." >&2
  exit 1
fi

# -------------------------------------------------------------------------- build
if [[ "$REFRESH" == "1" || ! -f .next/BUILD_ID ]]; then
  echo "Building the site…"
  if ! npm run build > "$SITE/.preview-build.log" 2>&1; then
    echo "Build failed. Last 30 lines:" >&2
    tail -30 "$SITE/.preview-build.log" >&2
    exit 1
  fi
  echo "Built."
fi

# -------------------------------------------------------------------------- serve
echo
echo "-----------------------------------------------------------------"
echo "  Meetbeatz preview        http://localhost:$PORT"
echo "  Producer sign-in         http://localhost:$PORT/admin/login"
echo "    email                  $ADMIN_EMAIL"
echo "    password               $ADMIN_PASSWORD"
echo "  Installable web app      open it on a phone and choose 'Install app'"
echo "  Payments                 simulation mode (no real charges)"
echo "  Database                 embedded Postgres, seeded demo data only"
echo "-----------------------------------------------------------------"
echo

exec npx next start -H 0.0.0.0 -p "$PORT"
