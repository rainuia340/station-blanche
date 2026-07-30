#!/usr/bin/env bash
set -euo pipefail

echo "[clamav] Configuration de ClamAV..."

# Désactiver le daemon (scan à la demande uniquement)
systemctl stop clamav-daemon 2>/dev/null || true
systemctl disable clamav-daemon 2>/dev/null || true

# Activer freshclam pour les mises à jour de signatures (admin active le réseau)
systemctl enable clamav-freshclam 2>/dev/null || true

# Mise à jour initiale des signatures si le réseau est disponible
if ping -c1 -W3 8.8.8.8 &>/dev/null; then
    echo "[clamav] Réseau détecté — mise à jour des signatures..."
    freshclam 2>/dev/null || echo "[clamav] freshclam a échoué (réseau ou miroir indisponible)."
else
    echo "[clamav] Pas de réseau — signatures non mises à jour (normal en station isolée)."
fi

echo "[clamav] Configuration terminée."
