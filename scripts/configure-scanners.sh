#!/usr/bin/env bash
# Installation et configuration des moteurs antivirus
set -euo pipefail

echo "[scanners] Configuration des moteurs antivirus..."

export DEBIAN_FRONTEND=noninteractive

# --- ClamAV ---
echo "[scanners] ClamAV..."
systemctl stop clamav-daemon 2>/dev/null || true
systemctl disable clamav-daemon 2>/dev/null || true
systemctl enable clamav-freshclam 2>/dev/null || true

if ping -c1 -W3 8.8.8.8 &>/dev/null; then
    freshclam 2>/dev/null || echo "[scanners] freshclam indisponible (réseau ou miroir)."
fi

# --- Linux Malware Detect (LMD / maldet) ---
install_maldet() {
    if [[ -f /usr/local/sbin/maldet ]]; then
        echo "[scanners] maldet déjà installé."
        return 0
    fi

    echo "[scanners] Installation de Linux Malware Detect (maldet)..."
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir"

    if ! wget -q -O maldet.tar.gz "http://www.rfxn.com/downloads/maldetect-current.tar.gz"; then
        echo "[scanners] ATTENTION : téléchargement maldet échoué (réseau requis à l'installation)."
        rm -rf "$tmpdir"
        return 1
    fi

    tar -xzf maldet.tar.gz
    cd maldetect-*
    ./install.sh

    # Activer la quarantaine automatique
    if [[ -f /usr/local/maldetect/conf.maldet ]]; then
        sed -i 's/^quarantine_hits=.*/quarantine_hits="1"/' /usr/local/maldetect/conf.maldet
    fi

    if ping -c1 -W3 8.8.8.8 &>/dev/null; then
        /usr/local/sbin/maldet -u 2>/dev/null || true
    fi

    rm -rf "$tmpdir"
    echo "[scanners] maldet installé."
}

# --- F-Prot Antivirus (gratuit usage personnel) ---
install_fprot() {
  if [[ -f /opt/f-prot/fpscan ]] || [[ -f /usr/local/f-prot/fpscan ]]; then
        echo "[scanners] F-Prot déjà installé."
        return 0
    fi

    echo "[scanners] Installation de F-Prot Antivirus..."
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir"

    local url="https://www.f-prot.com/download/home_users/linux_64.tar.gz"
    if ! wget -q -O fprot.tar.gz "$url"; then
        echo "[scanners] ATTENTION : téléchargement F-Prot échoué (réseau requis à l'installation)."
        rm -rf "$tmpdir"
        return 1
    fi

    tar -xzf fprot.tar.gz
    local installer
    installer=$(find . -name "install-f-prot.sh" -o -name "install.sh" | head -1)
    if [[ -z "$installer" ]]; then
        echo "[scanners] ATTENTION : script d'installation F-Prot introuvable."
        rm -rf "$tmpdir"
        return 1
    fi

  chmod +x "$installer"
  # Installation silencieuse vers /opt/f-prot ou /usr/local/f-prot
  yes "" | bash "$installer" 2>/dev/null || bash "$installer" </dev/null || true

    if ping -c1 -W3 8.8.8.8 &>/dev/null; then
        local updater
        updater=$(find /opt/f-prot /usr/local/f-prot -name "fp-update" 2>/dev/null | head -1)
        [[ -n "$updater" ]] && "$updater" 2>/dev/null || true
    fi

    rm -rf "$tmpdir"
    echo "[scanners] F-Prot installé."
}

install_maldet || true
install_fprot || true

mkdir -p /var/lib/antivirscan/quarantine
chmod 750 /var/lib/antivirscan/quarantine

echo "[scanners] Moteurs disponibles :"
[[ -f /usr/bin/clamscan ]] && echo "  ✓ ClamAV"
[[ -f /usr/local/sbin/maldet ]] && echo "  ✓ Linux Malware Detect (LMD)"
[[ -f /opt/f-prot/fpscan || -f /usr/local/f-prot/fpscan ]] && echo "  ✓ F-Prot Antivirus"

echo "[scanners] Configuration terminée."
echo "[scanners] Note : NOD32 et Avast ne proposent pas de scanner CLI gratuit pour Linux."
