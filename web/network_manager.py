"""Gestion réseau via NetworkManager (nmcli)."""

import re
import subprocess
from typing import Any

DEVICE_NAME_RE = re.compile(r"^[a-zA-Z0-9._-]+$")


def _run(args: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["nmcli", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _parse_nmcli_output(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in text.splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            result[key] = value
    return result


def _validate_device(device: str) -> str:
    if not device or not DEVICE_NAME_RE.match(device):
        raise ValueError("Nom d'interface invalide")
    return device


def is_available() -> bool:
    try:
        proc = _run(["--version"], timeout=5)
        return proc.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def list_devices() -> list[dict[str, Any]]:
    proc = _run(["-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device", "status"])
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "Impossible de lister les interfaces")

    devices = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split(":")
        if len(parts) < 4:
            continue
        device, dtype, state, connection = parts[0], parts[1], parts[2], ":".join(parts[3:])
        info: dict[str, Any] = {
            "device": device,
            "type": dtype,
            "type_label": "Wi-Fi" if dtype == "wifi" else "Ethernet" if dtype == "ethernet" else dtype,
            "state": state,
            "connection": connection or None,
            "enabled": state not in ("unavailable", "unmanaged"),
            "connected": state == "connected",
            "ipv4_method": None,
            "ipv4_address": None,
            "ipv4_gateway": None,
            "ipv4_dns": None,
        }

        if connection:
            conn_proc = _run(["-t", "connection", "show", connection])
            if conn_proc.returncode == 0:
                conn = _parse_nmcli_output(conn_proc.stdout)
                info["ipv4_method"] = conn.get("ipv4.method", "auto")
                info["ipv4_address"] = conn.get("IP4.ADDRESS", "").split("/")[0] or None
                info["ipv4_gateway"] = conn.get("IP4.GATEWAY") or conn.get("ipv4.gateway") or None
                dns = conn.get("IP4.DNS") or conn.get("ipv4.dns")
                info["ipv4_dns"] = dns.replace("|", ", ") if dns else None
                if info["ipv4_method"] == "manual" and conn.get("ipv4.addresses"):
                    info["ipv4_address"] = conn.get("ipv4.addresses", "").split("/")[0]

        devices.append(info)

    return devices


def set_device_state(device: str, enabled: bool) -> tuple[bool, str]:
    device = _validate_device(device)
    action = "connect" if enabled else "disconnect"
    proc = _run(["device", action, device])
    ok = proc.returncode == 0
    msg = (proc.stdout + proc.stderr).strip() or ("OK" if ok else "Échec")
    return ok, msg


def set_wifi_radio(enabled: bool) -> tuple[bool, str]:
    state = "on" if enabled else "off"
    proc = _run(["radio", "wifi", state])
    ok = proc.returncode == 0
    msg = (proc.stdout + proc.stderr).strip() or f"Wi-Fi {'activé' if enabled else 'désactivé'}"
    return ok, msg


def get_wifi_radio() -> bool:
    proc = _run(["radio", "wifi"])
    if proc.returncode != 0:
        proc = _run(["radio"])
    if proc.returncode != 0:
        return False
    text = proc.stdout.lower()
    return "enabled" in text or ":yes" in text


def configure_ipv4(
    device: str,
    method: str,
    address: str | None = None,
    prefix: int = 24,
    gateway: str | None = None,
    dns: str | None = None,
) -> tuple[bool, str]:
    device = _validate_device(device)
    if method not in ("auto", "manual", "disabled"):
        raise ValueError("Méthode IPv4 invalide")

    out = _run(["-g", "GENERAL.TYPE,GENERAL.CONNECTION", "device", "show", device])
    if out.returncode != 0:
        raise RuntimeError("Interface introuvable")

    lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    dtype = lines[0] if lines else "ethernet"
    connection = lines[1] if len(lines) > 1 else ""

    if not connection or connection == "--":
        connection = f"station-blanche-{device}"
        conn_type = "wifi" if dtype == "wifi" else "ethernet"
        create = _run([
            "connection", "add", "type", conn_type,
            "ifname", device, "con-name", connection,
        ])
        if create.returncode != 0:
            raise RuntimeError(create.stderr or "Impossible de créer la connexion")

    if method == "disabled":
        proc = _run(["device", "disconnect", device])
        return proc.returncode == 0, (proc.stdout + proc.stderr).strip()

    args = ["connection", "modify", connection, "ipv4.method", method]
    if method == "manual":
        if not address:
            raise ValueError("Adresse IP requise en mode fixe")
        args.extend(["ipv4.addresses", f"{address}/{prefix}"])
        if gateway:
            args.extend(["ipv4.gateway", gateway])
        if dns:
            args.extend(["ipv4.dns", dns.replace(",", " ")])
    else:
        args.extend(["ipv4.method", "auto"])

    mod = _run(args)
    if mod.returncode != 0:
        return False, mod.stderr or "Échec de la configuration"

    up = _run(["connection", "up", connection])
    ok = up.returncode == 0
    return ok, (up.stdout + up.stderr).strip() or "Configuration appliquée"


def wifi_scan(device: str | None = None) -> list[dict[str, Any]]:
    if device:
        device = _validate_device(device)
        _run(["device", "wifi", "rescan", "ifname", device], timeout=15)
    else:
        _run(["device", "wifi", "rescan"], timeout=15)

    args = ["-t", "-f", "SSID,SIGNAL,SECURITY,IN-USE", "device", "wifi", "list"]
    if device:
        args.extend(["ifname", device])

    proc = _run(args, timeout=20)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or "Scan Wi-Fi échoué")

    networks: list[dict[str, Any]] = []
    seen: set[str] = set()
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        # SSID peut contenir ':' — on parse depuis la droite
        parts = line.rsplit(":", 3)
        if len(parts) < 4:
            continue
        ssid_raw, signal_s, security, in_use = parts[0], parts[1], parts[2], parts[3]
        ssid = ssid_raw.replace("\\:", ":").replace("\\\\", "\\") or "(réseau caché)"
        if ssid in seen and ssid != "(réseau caché)":
            continue
        seen.add(ssid)
        networks.append({
            "ssid": ssid,
            "signal": int(signal_s) if signal_s.isdigit() else 0,
            "security": security or "—",
            "in_use": in_use == "*",
        })

    networks.sort(key=lambda n: n["signal"], reverse=True)
    return networks


def wifi_connect(
    ssid: str,
    password: str | None = None,
    device: str | None = None,
) -> tuple[bool, str]:
    if not ssid or len(ssid) > 64:
        raise ValueError("SSID invalide")
    if device:
        device = _validate_device(device)

    set_wifi_radio(True)

    args = ["device", "wifi", "connect", ssid]
    if password:
        args.extend(["password", password])
    if device:
        args.extend(["ifname", device])

    proc = _run(args, timeout=45)
    ok = proc.returncode == 0
    msg = (proc.stdout + proc.stderr).strip()
    return ok, msg or ("Connecté" if ok else "Échec de connexion")
