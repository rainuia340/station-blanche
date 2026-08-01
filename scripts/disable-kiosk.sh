#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/station-blanche"
STATION_USER="station"
AUTOSTART="/home/${STATION_USER}/.config/autostart/firefox-kiosk.desktop"
BROWSER=$("$REPO_DIR/scripts/browser.sh")

echo "[kiosk] Désactivation du mode kiosk..."

pkill -f "${BROWSER}.*kiosk" 2>/dev/null || pkill "$BROWSER" 2>/dev/null || true

if [[ -f "$AUTOSTART" ]]; then
    mv "$AUTOSTART" "${AUTOSTART}.disabled"
fi

# Ouvre Firefox en mode normal sur l'interface admin
sudo -u "$STATION_USER" DISPLAY=:0 "$BROWSER" "http://127.0.0.1:8080/admin" &

echo "[kiosk] Mode kiosk désactivé. Bureau accessible."
