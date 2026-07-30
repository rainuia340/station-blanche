#!/usr/bin/env bash
# Station Blanche — script d'installation pour Peppermint OS
# Usage :
#   curl -fsSL https://raw.githubusercontent.com/rainuia340/station-blanche/main/install.sh | sudo bash
#   curl -fsSL ... | sudo bash -s -- --update

set -euo pipefail

REPO_URL="https://github.com/rainuia340/station-blanche.git"
INSTALL_DIR="/opt/station-blanche"
LOG_FILE="/var/log/station-blanche-install.log"

DO_UPDATE=false
DO_HARDENING=true

usage() {
    cat <<'EOF'
Station Blanche — Installation Peppermint OS

Usage:
  install.sh [OPTIONS]

Options:
  --update         Met à jour depuis le dépôt GitHub et réinstalle les composants
  --no-hardening   Installe les outils sans appliquer le durcissement système
  -h, --help       Affiche cette aide

Exemples:
  curl -fsSL https://raw.githubusercontent.com/rainuia340/station-blanche/main/install.sh | sudo bash
  curl -fsSL ... | sudo bash -s -- --update
EOF
}

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg" | tee -a "$LOG_FILE"
}

die() {
    log "ERREUR: $*"
    exit 1
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --update)       DO_UPDATE=true; shift ;;
            --no-hardening) DO_HARDENING=false; shift ;;
            -h|--help)      usage; exit 0 ;;
            *)              die "Option inconnue : $1 (utilisez --help)" ;;
        esac
    done
}

check_root() {
    [[ $EUID -eq 0 ]] || die "Ce script doit être exécuté en root (sudo)."
}

check_os() {
    if [[ -f /etc/os-release ]]; then
        # shellcheck source=/dev/null
        source /etc/os-release
        log "Système détecté : ${PRETTY_NAME:-inconnu}"
    else
        die "Impossible de détecter le système d'exploitation."
    fi

    if ! grep -qiE 'peppermint|debian|ubuntu' /etc/os-release 2>/dev/null; then
        log "ATTENTION : ce script est conçu pour Peppermint OS (Debian). Poursuite à vos risques."
    fi
}

install_prerequisites() {
    log "Installation des prérequis système..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq \
        git curl ca-certificates \
        firefox \
        python3 python3-flask python3-pyudev python3-psutil \
        clamav clamav-freshclam \
        ntfs-3g exfatprogs \
        ufw auditd rsyslog \
        xfconf \
        > /dev/null
    log "Prérequis installés."
}

fetch_repo() {
    log "Récupération du dépôt GitHub : $REPO_URL"

    if [[ -d "$INSTALL_DIR/.git" ]]; then
        if $DO_UPDATE; then
            log "Mise à jour du dépôt existant..."
            git -C "$INSTALL_DIR" fetch origin main
            git -C "$INSTALL_DIR" reset --hard origin/main
        else
            log "Dépôt déjà présent dans $INSTALL_DIR (utilisez --update pour forcer la MAJ)."
        fi
    else
        log "Clonage du dépôt..."
        rm -rf "$INSTALL_DIR"
        git clone --depth 1 --branch main "$REPO_URL" "$INSTALL_DIR"
    fi

    [[ -d "$INSTALL_DIR/scripts" ]] || die "Dépôt incomplet : répertoire scripts/ introuvable."
}

run_install_scripts() {
    local scripts=(
        "scripts/configure-users.sh"
        "scripts/configure-web.sh"
        "scripts/configure-clamav.sh"
        "scripts/configure-autostart.sh"
        "scripts/apply-wallpaper.sh"
    )

    if $DO_HARDENING; then
        scripts+=("scripts/configure-hardening.sh")
    fi

    for script in "${scripts[@]}"; do
        local path="$INSTALL_DIR/$script"
        [[ -f "$path" ]] || die "Script manquant : $script"
        log "Exécution de $script..."
        bash "$path" 2>&1 | tee -a "$LOG_FILE"
    done
}

show_summary() {
    cat <<EOF

╔══════════════════════════════════════════════════════════════╗
║           Station Blanche — Installation terminée            ║
╠══════════════════════════════════════════════════════════════╣
║  Interface web  : http://127.0.0.1:8080/
║  Dépôt local    : $INSTALL_DIR
║  Logs install   : $LOG_FILE
║  Logs analyses  : /var/log/antivirscan/
║  Quarantaine    : /var/lib/antivirscan/quarantine/
║
║  Admin web      : admin / admin (à changer !)
║  Redémarrer     : sudo reboot
║  Mettre à jour  : sudo $INSTALL_DIR/install.sh --update
╚══════════════════════════════════════════════════════════════╝

EOF
}

main() {
    parse_args "$@"
    check_root
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"

    log "=== Début installation Station Blanche ==="
    check_os
    install_prerequisites
    fetch_repo
    run_install_scripts
    log "=== Installation terminée avec succès ==="
    show_summary
}

main "$@"
