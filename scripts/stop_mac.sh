#!/usr/bin/env bash
# Stop FinAlly (macOS/Linux). Idempotent. The data volume is kept.
set -euo pipefail

CONTAINER="finally"

if docker container inspect "$CONTAINER" >/dev/null 2>&1; then
  docker rm -f "$CONTAINER" >/dev/null
  echo "Stopped and removed container '$CONTAINER'. Data volume 'finally-data' is preserved."
else
  echo "Container '$CONTAINER' is not running."
fi
