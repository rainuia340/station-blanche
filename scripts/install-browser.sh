#!/usr/bin/env bash
# Installe un navigateur compatible kiosk (firefox-esr sur Debian/Peppermint)
set -euo pipefail

BROWSER_FILE="/etc/station-blanche/browser"
INSTALL_DIR="${INSTALL_DIR:-/opt/station-blanche}"

log() { echo "[browser] $*"; }

save_browser() {
    local cmd="$1"
    mkdir -p /etc/station-blanche
    echo "$cmd" > "$BROWSER_FILE"
    chmod 644 "$BROWSER_FILE"
    log "Navigateur configuré : $cmd ($($cmd --version 2>/dev/null | head -1 || echo 'version inconnue'))"
}

try_install() {
    local pkg="$1"
    if apt-cache show "$pkg" &>/dev/null; then
        log "Installation du paquet $pkg..."
        DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$pkg" && return 0
    fi
    return 1
}

detect_installed() {
    for cmd in firefox-esr firefox chromium chromium-browser; do
        if command -v "$cmd" &>/dev/null; then
            echo "$cmd"
            return 0
        fi
    done
    return 1
}

install_mozilla_firefox() {
  log "Tentative d'ajout du dépôt Mozilla pour firefox..."
  install -d -m 0755 /etc/apt/keyrings
  if ! [[ -f /etc/apt/keyrings/packages.mozilla.org.asc ]]; then
    curl -fsSL https://packages.mozilla.org/apt/repo-signing-key.gpg \
      | gpg --dearmor -o /etc/apt/keyrings/packages.mozilla.org.asc 2>/dev/null \
      || wget -qO- https://packages.mozilla.org/apt/repo-signing-key.gpg \
      | gpg --dearmor -o /etc/apt/keyrings/packages.mozilla.org.asc 2>/dev/null \
      || return 1
  fi

  if ! [[ -f /etc/apt/sources.list.d/mozilla.list ]]; then
    echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" \
      > /etc/apt/sources.list.d/mozilla.list
  fi

  apt-get update -qq
  try_install firefox
}

# --- Installation ---
export DEBIAN_FRONTEND=noninteractive

if cmd=$(detect_installed); then
    log "Navigateur déjà présent : $cmd"
    save_browser "$cmd"
    exit 0
fi

# Peppermint / Debian Bookworm : firefox-esr dans les dépôts officiels
if try_install firefox-esr; then
    save_browser "firefox-esr"
    exit 0
fi

if try_install firefox; then
    save_browser "firefox"
    exit 0
fi

if install_mozilla_firefox && cmd=$(detect_installed); then
    save_browser "$cmd"
    exit 0
fi

# Dernier recours : Chromium
if try_install chromium || try_install chromium-browser; then
    cmd=$(detect_installed)
    save_browser "$cmd"
    exit 0
fi

log "ERREUR : impossible d'installer un navigateur (firefox-esr, firefox ou chromium)."
exit 1
