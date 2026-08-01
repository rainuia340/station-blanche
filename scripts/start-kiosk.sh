#!/usr/bin/env bash
# Attend que le serveur web soit prêt, puis lance Firefox en mode kiosk
set -euo pipefail

URL="http://127.0.0.1:8080/"

for _ in $(seq 1 60); do
    if curl -sf "$URL" >/dev/null 2>&1; then
        break
    fi
    sleep 1
done

exec firefox --kiosk "$URL"
