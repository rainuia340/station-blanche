#!/usr/bin/env bash
# Durcissement basé sur les recommandations ANSSI (niveau minimal/intermédiaire)
set -euo pipefail

echo "[hardening] Application du durcissement système..."

# --- Pare-feu : tout bloquer en entrée ---
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw --force enable
echo "[hardening] UFW activé (entrée : deny, sortie : allow)."

# --- Services inutiles désactivés ---
for svc in cups bluetooth avahi-daemon; do
    systemctl stop "$svc" 2>/dev/null || true
    systemctl disable "$svc" 2>/dev/null || true
done

# --- Paramètres noyau (sysctl) ---
SYSCTL_FILE="/etc/sysctl.d/99-station-blanche.conf"
cat > "$SYSCTL_FILE" <<'EOF'
# Station Blanche — durcissement noyau (ANSSI)
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.yama.ptrace_scope = 1
fs.suid_dumpable = 0
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.icmp_echo_ignore_broadcasts = 1
net.ipv4.conf.all.accept_redirects = 0
net.ipv4.conf.default.accept_redirects = 0
net.ipv4.conf.all.send_redirects = 0
net.ipv4.conf.default.send_redirects = 0
EOF
sysctl --system > /dev/null 2>&1 || true

# --- Auditd ---
systemctl enable auditd 2>/dev/null || true
systemctl start auditd 2>/dev/null || true

# --- Permissions sur les répertoires sensibles ---
chmod 700 /root
chmod 750 /var/log/antivirscan
chmod 750 /var/lib/antivirscan/quarantine

echo "[hardening] Durcissement terminé."
