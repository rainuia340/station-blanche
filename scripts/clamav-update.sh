#!/usr/bin/env bash
# Met à jour les signatures ClamAV (freshclam) de façon fiable.
set -euo pipefail

log() { echo "$*" >&2; }

find_freshclam() {
    local p
    for p in /usr/bin/freshclam /bin/freshclam; do
        if [[ -x "$p" ]]; then
            echo "$p"
            return 0
        fi
    done
    return 1
}

ensure_freshclam() {
    if find_freshclam &>/dev/null; then
        return 0
    fi
    log "freshclam introuvable — installation de clamav-freshclam..."
    export DEBIAN_FRONTEND=noninteractive
    apt-get update -qq
    apt-get install -y -qq clamav clamav-freshclam
}

stop_freshclam_service() {
    if systemctl is-active --quiet clamav-freshclam 2>/dev/null; then
        log "Arrêt temporaire du service clamav-freshclam..."
        systemctl stop clamav-freshclam
        echo 1
        return
    fi
    echo 0
}

start_freshclam_service() {
    if [[ "${1:-0}" == "1" ]]; then
        log "Redémarrage du service clamav-freshclam..."
        systemctl start clamav-freshclam 2>/dev/null || true
    fi
}

run_freshclam() {
    local bin="$1"
    mkdir -p /var/lib/clamav /var/log/clamav
    chown clamav:clamav /var/lib/clamav /var/log/clamav 2>/dev/null || true

    # --stdout : sortie visible dans les journaux / interface admin
    if "$bin" --stdout 2>&1; then
        return 0
    fi
    local rc=$?
    # Code 1 = déjà à jour sur certaines versions
    if [[ "$rc" -eq 1 ]] && [[ -f /var/lib/clamav/main.cvd || -f /var/lib/clamav/main.cld ]]; then
        log "Signatures ClamAV déjà à jour."
        return 0
    fi
    return "$rc"
}

main() {
    ensure_freshclam
    local bin
    bin=$(find_freshclam) || {
        log "ERREUR: freshclam toujours introuvable après installation."
        exit 1
    }

    local restart
    restart=$(stop_freshclam_service)
    trap 'start_freshclam_service "$restart"' EXIT

    log "--- ClamAV ($bin) ---"
    run_freshclam "$bin"
}

main "$@"
