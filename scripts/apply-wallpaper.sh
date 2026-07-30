#!/usr/bin/env bash
set -euo pipefail

WALLPAPER="${1:-/opt/station-blanche/web/static/img/wallpaper.svg}"
STATION_USER="station"

if [[ ! -f "$WALLPAPER" ]]; then
    echo "[wallpaper] Fichier introuvable : $WALLPAPER"
    exit 1
fi

# Appliquer le fond d'écran XFCE pour l'utilisateur station
sudo -u "$STATION_USER" DISPLAY=:0 xfconf-query \
    -c xfce4-desktop \
    -p /backdrop/screen0/monitor0/workspace0/last-image \
    -s "$WALLPAPER" 2>/dev/null || true

sudo -u "$STATION_USER" DISPLAY=:0 xfconf-query \
    -c xfce4-desktop \
    -p /backdrop/screen0/monitor0/workspace0/image-style \
    -n -t int -s 5 2>/dev/null || true

echo "[wallpaper] Fond d'écran appliqué : $WALLPAPER"
