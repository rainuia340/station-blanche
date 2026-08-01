#!/usr/bin/env bash
set -euo pipefail

STATION_USER="station"

echo "[users] Configuration de l'utilisateur ${STATION_USER}..."

if ! id "$STATION_USER" &>/dev/null; then
    useradd -m -s /bin/bash -G plugdev "$STATION_USER"
    passwd -d "$STATION_USER" 2>/dev/null || true
    echo "[users] Compte ${STATION_USER} créé (auto-login kiosk, sans mot de passe)."
else
    echo "[users] Compte ${STATION_USER} déjà existant."
fi

# Pas de droits sudo pour l'utilisateur kiosk
if getent group sudo | grep -q "$STATION_USER"; then
    deluser "$STATION_USER" sudo 2>/dev/null || true
fi

echo "[users] L'authentification admin se fait via l'interface web (admin / admin par défaut)."
