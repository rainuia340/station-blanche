#!/usr/bin/env bash
# Met à jour les signatures de tous les moteurs antivirus installés
set -euo pipefail

echo "=== Mise à jour des signatures antivirus ==="

if command -v freshclam &>/dev/null; then
    echo "--- ClamAV (freshclam) ---"
    freshclam 2>&1 || echo "Échec freshclam"
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
