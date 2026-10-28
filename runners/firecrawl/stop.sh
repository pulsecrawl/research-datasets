#!/bin/sh
set -eu
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
RESEARCH=$(CDPATH= cd -- "$HERE/../.." && pwd)
CHECKOUT=${FIRECRAWL_CHECKOUT:-"$RESEARCH/.cache/firecrawl-v2.9.0"}
docker compose -f "$CHECKOUT/docker-compose.yaml" -f "$HERE/compose.yaml" down --remove-orphans
