"""Gestion des volumes BitLocker via dislocker."""

from __future__ import annotations

import os
import re
import subprocess
import threading
import time
from typing import Any

DISLOCKER_BIN = "/usr/bin/dislocker"
BITLOCKER_WORK_BASE = "/mnt/station-blanche-bitlocker"
SCAN_MOUNT = "/mnt/station-blanche-scan"
DISLOCKER_FILE = "dislocker-file"

_lock = threading.Lock()
_unlocked: dict[str, dict[str, str]] = {}


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def is_available() -> bool:
    return os.path.isfile(DISLOCKER_BIN)


def _device_id(device: str) -> str:
    return os.path.basename(device)


def _work_dir(device: str) -> str:
    return os.path.join(BITLOCKER_WORK_BASE, _device_id(device))


def _normalize_recovery_key(key: str) -> str:
    return re.sub(r"[\s\-]", "", key.strip())


def is_bitlocker_partition(device: str) -> bool:
    if not device or not os.path.exists(device):
        return False

    proc = _run(["blkid", "-o", "value", "-s", "TYPE", device])
    if proc.returncode == 0 and "bitlocker" in proc.stdout.lower():
        return True

    if is_available():
        proc = _run([DISLOCKER_BIN, "-c", "-V", device], timeout=30)
        return proc.returncode == 0

    return False


def get_state(device: str) -> dict[str, Any]:
    with _lock:
        info = _unlocked.get(device)
    if info and os.path.ismount(info["mountpoint"]):
        return {
            "unlocked": True,
            "mountpoint": info["mountpoint"],
            "work_dir": info["work_dir"],
        }
    return {"unlocked": False, "mountpoint": None, "work_dir": None}


def is_unlocked(device: str) -> bool:
    return get_state(device)["unlocked"]


def get_unlocked_mount(device: str) -> str | None:
    state = get_state(device)
    return state["mountpoint"] if state["unlocked"] else None


def _cleanup_mounts(device: str | None = None) -> None:
    if os.path.ismount(SCAN_MOUNT):
        _run(["umount", SCAN_MOUNT])

    targets: list[str]
    if device:
        targets = [_work_dir(device)]
    else:
        targets = []
        if os.path.isdir(BITLOCKER_WORK_BASE):
            for name in os.listdir(BITLOCKER_WORK_BASE):
                targets.append(os.path.join(BITLOCKER_WORK_BASE, name))

    for work_dir in targets:
        if os.path.ismount(work_dir):
            _run(["umount", work_dir])


def _wait_for_dislocker_file(work_dir: str, timeout: int = 60) -> bool:
    path = os.path.join(work_dir, DISLOCKER_FILE)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if os.path.isfile(path):
            return True
        time.sleep(0.5)
    return False


def unlock(
    device: str,
    password: str | None = None,
    recovery_key: str | None = None,
) -> tuple[bool, str]:
    if not is_available():
        return False, "dislocker n'est pas installé (paquet dislocker requis)."

    if not os.path.exists(device):
        return False, f"Périphérique introuvable : {device}"

    if not is_bitlocker_partition(device):
        return False, "Ce volume ne semble pas chiffré avec BitLocker."

    password = (password or "").strip()
    recovery_key = _normalize_recovery_key(recovery_key or "")

    if not password and not recovery_key:
        return False, "Indiquez le mot de passe BitLocker ou la clé de récupération."

    if recovery_key and not re.fullmatch(r"\d{48}", recovery_key):
        return False, "La clé de récupération doit contenir 48 chiffres."

    work_dir = _work_dir(device)
    os.makedirs(BITLOCKER_WORK_BASE, exist_ok=True)
    os.makedirs(work_dir, exist_ok=True)

    with _lock:
        for other_device in list(_unlocked):
            lock(other_device)

    _cleanup_mounts(device)

    cmd = [DISLOCKER_BIN, "-V", device]
    if recovery_key:
        cmd.append(f"-r{recovery_key}")
    else:
        cmd.append(f"-p{password}")
    cmd.extend(["--", work_dir])

    proc = _run(cmd, timeout=180)
    if proc.returncode != 0:
        _cleanup_mounts(device)
        err = (proc.stderr or proc.stdout or "Échec du déverrouillage BitLocker.").strip()
        if "wrong" in err.lower() or "incorrect" in err.lower() or "failed" in err.lower():
            return False, "Mot de passe ou clé de récupération incorrect(e)."
        return False, err

    if not _wait_for_dislocker_file(work_dir):
        _cleanup_mounts(device)
        return False, "Fichier dislocker introuvable après déverrouillage."

    dislocker_path = os.path.join(work_dir, DISLOCKER_FILE)
    os.makedirs(SCAN_MOUNT, exist_ok=True)
    mount_proc = _run(["mount", "-o", "loop,ro", dislocker_path, SCAN_MOUNT])
    if mount_proc.returncode != 0:
        _cleanup_mounts(device)
        err = mount_proc.stderr.strip() or "Impossible de monter le volume déchiffré."
        return False, err

    with _lock:
        _unlocked[device] = {
            "mountpoint": SCAN_MOUNT,
            "work_dir": work_dir,
        }

    return True, "Volume BitLocker déverrouillé."


def lock(device: str) -> tuple[bool, str]:
    with _lock:
        _unlocked.pop(device, None)

    _cleanup_mounts(device)
    work_dir = _work_dir(device)
    try:
        if os.path.isdir(work_dir) and not os.listdir(work_dir):
            os.rmdir(work_dir)
    except OSError:
        pass

    return True, "Volume BitLocker verrouillé."


def lock_all() -> None:
    with _lock:
        devices = list(_unlocked)
    for device in devices:
        lock(device)
