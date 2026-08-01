#!/usr/bin/env bash
set -euo pipefail

STATION_USER="station"
AUTOSTART="/home/${STATION_USER}/.config/autostart/firefox-kiosk.desktop"
INSTALL_DIR="/opt/station-blanche"

echo "[kiosk] Désactivation du mode kiosk..."

pkill -f "firefox.*kiosk" 2>/dev/null || pkill firefox 2>/dev/null || true

if [[ -f "$AUTOSTART" ]]; then
    mv "$AUTOSTART" "${AUTOSTART}.disabled"
fi

# Ouvre Firefox en mode normal sur l'interface admin
sudo -u "$STATION_USER" DISPLAY=:0 firefox "http://127.0.0.1:8080/admin" &

echo "[kiosk] Mode kiosk désactivé. Bureau accessible."
