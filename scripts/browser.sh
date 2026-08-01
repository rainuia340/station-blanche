#!/usr/bin/env bash
# Retourne la commande du navigateur kiosk configuré
set -euo pipefail

BROWSER_FILE="/etc/station-blanche/browser"

resolve_browser() {
    if [[ -f "$BROWSER_FILE" ]]; then
        local cmd
        cmd=$(tr -d '[:space:]' < "$BROWSER_FILE")
        if [[ -n "$cmd" ]] && command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return 0
        fi
    fi

    for cmd in firefox-esr firefox chromium chromium-browser; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return 0
        fi
    done

    return 1
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    resolve_browser || { echo "firefox-esr" >&2; exit 1; }
fi
