#!/usr/bin/env bash
set -euo pipefail

STATION_USER="station"
AUTOSTART="/home/${STATION_USER}/.config/autostart/firefox-kiosk.desktop"
REPO_DIR="/opt/station-blanche"

echo "[kiosk] Réactivation du mode kiosk..."

if [[ -f "${AUTOSTART}.disabled" ]]; then
    mv "${AUTOSTART}.disabled" "$AUTOSTART"
elif [[ ! -f "$AUTOSTART" ]]; then
    cp "${REPO_DIR}/config/firefox-kiosk.desktop" "$AUTOSTART"
    chown "${STATION_USER}:${STATION_USER}" "$AUTOSTART"
fi

pkill firefox 2>/dev/null || true
sleep 1

sudo -u "$STATION_USER" DISPLAY=:0 bash "${REPO_DIR}/scripts/start-kiosk.sh" &

echo "[kiosk] Mode kiosk réactivé."
