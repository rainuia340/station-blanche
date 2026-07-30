#!/usr/bin/env bash
set -euo pipefail

STATION_USER="station"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUTOSTART_DIR="/home/${STATION_USER}/.config/autostart"

echo "[autostart] Configuration auto-login et mode kiosk..."

# Auto-login lightdm
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
if [[ -f "$LIGHTDM_CONF" ]]; then
    if grep -q "^\[Seat:\*\]" "$LIGHTDM_CONF"; then
        if ! grep -q "^autologin-user=" "$LIGHTDM_CONF"; then
            sed -i "/^\[Seat:\*\]/a autologin-user=${STATION_USER}\nautologin-user-timeout=0" "$LIGHTDM_CONF"
        else
            sed -i "s/^#*autologin-user=.*/autologin-user=${STATION_USER}/" "$LIGHTDM_CONF"
            sed -i "s/^#*autologin-user-timeout=.*/autologin-user-timeout=0/" "$LIGHTDM_CONF"
        fi
    fi
    echo "[autostart] Auto-login configuré pour ${STATION_USER}."
fi

# Autostart Firefox kiosk
mkdir -p "$AUTOSTART_DIR"
cp "$REPO_DIR/config/firefox-kiosk.desktop" "$AUTOSTART_DIR/"
chmod +x "$REPO_DIR/scripts/start-kiosk.sh"
chown -R "${STATION_USER}:${STATION_USER}" "/home/${STATION_USER}/.config"

echo "[autostart] Firefox kiosk configuré au démarrage."
