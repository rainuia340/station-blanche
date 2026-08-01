#!/usr/bin/env bash
# Met à jour les signatures de tous les moteurs antivirus installés
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Mise à jour des signatures antivirus ==="

if [[ -x "$SCRIPT_DIR/clamav-update.sh" ]]; then
    bash "$SCRIPT_DIR/clamav-update.sh" || echo "Échec mise à jour ClamAV"
elif command -v freshclam &>/dev/null; then
    echo "--- ClamAV (freshclam) ---"
    systemctl stop clamav-freshclam 2>/dev/null || true
    freshclam --stdout 2>&1 || echo "Échec freshclam"
    systemctl start clamav-freshclam 2>/dev/null || true
else
    echo "--- ClamAV ---"
    echo "freshclam introuvable (installez clamav-freshclam)"
fi

if [[ -f /usr/local/sbin/maldet ]]; then
    echo "--- Linux Malware Detect (maldet -u) ---"
    /usr/local/sbin/maldet -u 2>&1 || echo "Échec maldet"
fi

FPROT_UPDATE=""
for path in /opt/f-prot/fp-update /usr/local/f-prot/fp-update; do
    [[ -f "$path" ]] && FPROT_UPDATE="$path" && break
done

if [[ -n "$FPROT_UPDATE" ]]; then
    echo "--- F-Prot (fp-update) ---"
    "$FPROT_UPDATE" 2>&1 || echo "Échec F-Prot"
fi

echo "=== Mise à jour terminée ==="
