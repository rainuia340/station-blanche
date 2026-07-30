#!/usr/bin/env bash
set -euo pipefail

echo "[network] Configuration NetworkManager..."

systemctl enable NetworkManager 2>/dev/null || true
systemctl start NetworkManager 2>/dev/null || true

if command -v nmcli &>/dev/null; then
    echo "[network] NetworkManager actif (nmcli disponible)."
else
    echo "[network] ATTENTION : nmcli introuvable. Installez network-manager."
fi
