#!/bin/sh
set -eu

VERSION="v2.9.0"
COMMIT="11490b52b46b35423548df809c966d51463ec49d"
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RESEARCH=$(CDPATH= cd -- "$HERE/../.." && pwd)
CHECKOUT=${FIRECRAWL_CHECKOUT:-"$RESEARCH/.cache/firecrawl-$VERSION"}

if ! command -v git >/dev/null || ! command -v docker >/dev/null || ! command -v python3 >/dev/null; then
  echo "git, Python 3, and Docker Compose v2 are required" >&2
  exit 2
fi
if [ ! -d "$CHECKOUT/.git" ]; then
  mkdir -p "$(dirname -- "$CHECKOUT")"
  git clone --filter=blob:none --no-checkout https://github.com/firecrawl/firecrawl.git "$CHECKOUT"
  git -C "$CHECKOUT" fetch --depth=1 origin "$COMMIT"
  git -C "$CHECKOUT" checkout --detach "$COMMIT"
fi
ACTUAL=$(git -C "$CHECKOUT" rev-parse HEAD)
if [ "$ACTUAL" != "$COMMIT" ]; then
  echo "Firecrawl checkout mismatch: expected $COMMIT, got $ACTUAL" >&2
  exit 3
fi

export USE_DB_AUTHENTICATION=false
export LOGGING_LEVEL=ERROR
if ! docker compose \
  -f "$CHECKOUT/docker-compose.yaml" \
  -f "$HERE/compose.yaml" \
  config --format json | python3 -c '
import json, sys
services = json.load(sys.stdin)["services"]
unsafe = sorted(name for name, value in services.items() if value.get("logging", {}).get("driver") != "none")
if unsafe:
    raise SystemExit("persistent Docker logging is enabled for: " + ", ".join(unsafe))
'; then
  echo "Refusing to start Firecrawl without logging=none on every service" >&2
  exit 4
fi
docker compose \
  -f "$CHECKOUT/docker-compose.yaml" \
  -f "$HERE/compose.yaml" \
  up --detach --build

attempt=0
until curl --fail --silent --show-error http://127.0.0.1:3002/v0/health/liveness >/dev/null 2>&1; do
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 120 ]; then
    echo "Firecrawl did not become ready; inspect with docker compose ps (container logging is disabled)" >&2
    exit 5
  fi
  sleep 2
done
echo "Firecrawl $VERSION ($COMMIT) is ready at http://127.0.0.1:3002"
