#!/usr/bin/env bash
# Désinstalle Station Blanche et restaure Peppermint en configuration normale.
# Usage : sudo /opt/station-blanche/scripts/uninstall.sh [--reboot]

set -euo pipefail

INSTALL_DIR="/opt/station-blanche"
STATION_USER="station"
CONFIG_DIR="/etc/station-blanche"
SERVICE_NAME="station-blanche-web"
LOG_FILE="/var/log/station-blanche-uninstall.log"
DO_REBOOT=false

[[ $EUID -eq 0 ]] || { echo "Exécuter en root (sudo)."; exit 1; }

while [[ $# -gt 0 ]]; do
    case "$1" in
        --reboot) DO_REBOOT=true; shift ;;
        *) shift ;;
    esac
done

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log "=== Début désinstallation Station Blanche ==="

# Laisser le temps à l'API web de répondre si lancé depuis l'admin
sleep 2

# Arrêter Firefox kiosk
pkill -u "$STATION_USER" firefox 2>/dev/null || pkill firefox 2>/dev/null || true

# Arrêter et supprimer le service web
if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
    systemctl stop "$SERVICE_NAME"
fi
systemctl disable "$SERVICE_NAME" 2>/dev/null || true
rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
systemctl daemon-reload

# Supprimer l'auto-login lightdm
LIGHTDM_CONF="/etc/lightdm/lightdm.conf"
if [[ -f "$LIGHTDM_CONF" ]]; then
    sed -i "/^autologin-user=${STATION_USER}/d" "$LIGHTDM_CONF"
    sed -i '/^autologin-user-timeout=0$/d' "$LIGHTDM_CONF"
    log "Auto-login lightdm supprimé."
fi

# Supprimer l'utilisateur station
if id "$STATION_USER" &>/dev/null; then
    pkill -u "$STATION_USER" 2>/dev/null || true
    sleep 1
    userdel -r "$STATION_USER" 2>/dev/null || userdel "$STATION_USER" 2>/dev/null || true
    log "Utilisateur ${STATION_USER} supprimé."
fi

# Restaurer les services désactivés par le durcissement
for svc in cups bluetooth avahi-daemon; do
    systemctl enable "$svc" 2>/dev/null || true
done

# Supprimer le durcissement sysctl
rm -f /etc/sysctl.d/99-station-blanche.conf
sysctl --system > /dev/null 2>&1 || true

# Désactiver UFW (état Peppermint par défaut)
if command -v ufw &>/dev/null; then
    ufw --force disable 2>/dev/null || true
    log "UFW désactivé."
fi

# Supprimer les fichiers et répertoires Station Blanche
rm -rf "$CONFIG_DIR"
rm -rf /var/log/antivirscan
rm -rf /var/lib/antivirscan
rm -f /var/log/station-blanche-install.log

log "Fichiers de configuration supprimés."

# Supprimer le dépôt local (ce script inclus)
rm -rf "$INSTALL_DIR"
log "Dépôt ${INSTALL_DIR} supprimé."

log "=== Désinstallation terminée — Peppermint restauré ==="

if $DO_REBOOT; then
    log "Redémarrage dans 5 secondes..."
    sleep 5
    reboot
fi
