#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[web] Installation du service web..."

# Initialiser la configuration (admin/admin par défaut)
cd "$REPO_DIR/web"
python3 -c "from config_manager import ensure_config; ensure_config()"

# Installer le service systemd
cp "$REPO_DIR/systemd/station-blanche-web.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable station-blanche-web
systemctl restart station-blanche-web

# Répertoires de logs et quarantaine
mkdir -p /var/log/antivirscan /var/lib/antivirscan/quarantine
chmod 750 /var/log/antivirscan /var/lib/antivirscan/quarantine

echo "[web] Service web installé et démarré sur http://127.0.0.1:8080"
