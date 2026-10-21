#!/bin/sh
# Stage the static site (web/ plus the shared Python module) and serve it.
# Used by the Freebuff preview: PORT is injected by the platform.
set -e

PORT="${PORT:-8000}"
STAGE=".preview-site"

rm -rf "$STAGE"
mkdir -p "$STAGE"
cp web/* "$STAGE"/
cp duplicate_detector.py "$STAGE"/

exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory "$STAGE"
