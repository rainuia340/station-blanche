#!/usr/bin/env bash
# Attend que le serveur web soit prêt, puis lance le navigateur en mode kiosk
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/station-blanche}"
URL="http://127.0.0.1:8080/"

BROWSER=$("$REPO_DIR/scripts/browser.sh")

for _ in $(seq 1 60); do
    if curl -sf "$URL" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

exec "$BROWSER" --kiosk "$URL"
