"""Détection et montage des médias amovibles (USB, disques externes)."""

import os
import re
import subprocess
from typing import Any

import psutil
import pyudev

MOUNT_BASE = "/mnt/station-blanche-scan"
SUPPORTED_FS = {
    "ntfs", "fuseblk", "ntfs-3g",
    "exfat", "vfat", "fat", "fat32",
    "ext4", "ext3", "ext2",
}
# Points de montage système à exclure
SYSTEM_MOUNTS = {"/", "/boot", "/boot/efi", "/var", "/usr", "/home", "/tmp"}


def _run(cmd: list[str], timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _disk_size_human(size_bytes: int) -> str:
    for unit in ("o", "Ko", "Mo", "Go", "To"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}" if unit == "o" else f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} Po"


def _get_root_disk() -> str | None:
    """Retourne le disque système (ex: sda) pour l'exclure."""
    for part in psutil.disk_partitions():
        if part.mountpoint == "/":
            name = os.path.basename(part.device)
            # sda1 -> sda, nvme0n1p1 -> nvme0n1
            return re.sub(r"p?\d+$", "", name)
    return None


def _is_removable(disk_name: str, udev_disk) -> bool:
    if udev_disk.get("ID_BUS") == "usb":
        return True
    removable_path = f"/sys/block/{disk_name}/removable"
    try:
        with open(removable_path) as f:
            return f.read().strip() == "1"
    except OSError:
        return False


def _get_serial(udev_dev) -> str:
    serial = (
        udev_dev.get("ID_SERIAL_SHORT")
        or udev_dev.get("ID_SERIAL")
        or udev_dev.get("ID_USB_SERIAL_NUM")
        or udev_dev.get("ID_MODEL")
        or "INCONNU"
    )
    return re.sub(r"[^\w\-]", "_", serial.strip())[:64] or "INCONNU"


def _get_fstype(device: str) -> str:
    proc = _run(["blkid", "-o", "value", "-s", "TYPE", device])
    return proc.stdout.strip().lower() if proc.returncode == 0 else ""


def _normalize_fstype(fstype: str) -> str:
    if fstype in ("fuseblk", "ntfs"):
        return "ntfs"
    return fstype


def refresh_devices() -> None:
    """Force la re-détection des périphériques."""
    _run(["udevadm", "settle"], timeout=15)
    _run(["partprobe"], timeout=10)


def list_media() -> list[dict[str, Any]]:
    """Liste les partitions scannables (hors disque système)."""
    refresh_devices()
    context = pyudev.Context()
    root_disk = _get_root_disk()
    media_list: list[dict[str, Any]] = []
    seen_devices: set[str] = set()

    def is_system_disk(disk_name: str) -> bool:
        return bool(root_disk and disk_name == root_disk)

    def add_media(device, disk_name, parent, label, serial, bus, fstype, size, mountpoint, mounted):
        if device in seen_devices:
            return
        seen_devices.add(device)
        media_list.append({
            "id": os.path.basename(device),
            "device": device,
            "disk": disk_name,
            "label": label or os.path.basename(device),
            "serial": serial,
            "fstype": fstype or "inconnu",
            "size": _disk_size_human(size),
            "size_bytes": size,
            "mountpoint": mountpoint,
            "mounted": mounted,
            "bus": bus,
            "removable": _is_removable(disk_name, parent) if parent else False,
        })

    # Partitions montées
    for part in psutil.disk_partitions(all=False):
        device = part.device
        disk_name = re.sub(r"p?\d+$", "", os.path.basename(device))
        if is_system_disk(disk_name):
            continue
        if part.mountpoint in SYSTEM_MOUNTS:
            continue

        fstype = _normalize_fstype(part.fstype.lower())
        if fstype not in SUPPORTED_FS:
            continue

        udev_part = pyudev.Devices.from_device_file(context, device)
        parent = udev_part.parent
        disk_udev_name = os.path.basename(parent.device_node) if parent and parent.device_node else disk_name

        try:
            with open(f"/sys/class/block/{os.path.basename(device)}/size") as f:
                size = int(f.read().strip()) * 512
        except OSError:
            size = 0

        add_media(
            device, disk_udev_name, parent,
            udev_part.get("ID_FS_LABEL") or udev_part.get("ID_MODEL"),
            _get_serial(parent) if parent else "INCONNU",
            (parent.get("ID_BUS") if parent else None) or "unknown",
            fstype or part.fstype, size, part.mountpoint, True,
        )

    # Partitions non montées (tous disques sauf système)
    for disk in context.list_devices(subsystem="block", DEVTYPE="disk"):
        disk_name = os.path.basename(disk.device_node)
        if is_system_disk(disk_name):
            continue

        serial = _get_serial(disk)
        bus = disk.get("ID_BUS") or "unknown"

        for part in context.list_devices(subsystem="block", DEVTYPE="partition", parent=disk):
            device = part.device_node
            if not device or device in seen_devices:
                continue

            fstype = _normalize_fstype(_get_fstype(device))
            if not fstype or fstype not in SUPPORTED_FS:
                continue

            try:
                with open(f"/sys/class/block/{os.path.basename(device)}/size") as f:
                    size = int(f.read().strip()) * 512
            except OSError:
                size = 0

            add_media(
                device, disk_name, disk,
                part.get("ID_FS_LABEL") or part.get("ID_MODEL"),
                serial, bus, fstype, size, None, False,
            )

    media_list.sort(key=lambda m: (not m["mounted"], m["disk"], m["device"]))
    return media_list


def mount_readonly(device: str) -> str:
    """Monte une partition en lecture seule, retourne le point de montage."""
    for part in psutil.disk_partitions():
        if part.device == device:
            return part.mountpoint

    os.makedirs(MOUNT_BASE, exist_ok=True)

    # Démontage propre si déjà utilisé
    _run(["umount", MOUNT_BASE])

    fstype = _get_fstype(device)
    mount_fstype = fstype
    if fstype in ("ntfs", "fuseblk"):
        mount_fstype = "ntfs-3g"
    elif fstype == "exfat":
        mount_fstype = "exfat"

    cmd = ["mount", "-o", "ro"]
    if mount_fstype:
        cmd.extend(["-t", mount_fstype])
    cmd.extend([device, MOUNT_BASE])

    proc = _run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"Impossible de monter {device}")

    return MOUNT_BASE


def unmount_if_temporary(mountpoint: str) -> None:
    """Démonte si monté sur notre point temporaire."""
    if mountpoint == MOUNT_BASE:
        _run(["umount", MOUNT_BASE])
