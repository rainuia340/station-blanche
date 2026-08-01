"""Détection et montage des médias amovibles (USB, disques externes)."""

import os
import re
import subprocess
from typing import Any

import psutil
import pyudev

from bitlocker_manager import (
    SCAN_MOUNT,
    get_state,
    is_bitlocker_partition,
    is_unlocked,
)

MOUNT_BASE = SCAN_MOUNT
SUPPORTED_FS = {
    "ntfs", "fuseblk", "ntfs-3g",
    "exfat", "vfat", "fat", "fat32",
    "ext4", "ext3", "ext2",
}
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
    for part in psutil.disk_partitions():
        if part.mountpoint == "/":
            name = os.path.basename(part.device)
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


def _partition_size(device: str) -> int:
    try:
        with open(f"/sys/class/block/{os.path.basename(device)}/size") as f:
            return int(f.read().strip()) * 512
    except OSError:
        return 0


def refresh_devices() -> None:
    _run(["udevadm", "settle"], timeout=15)
    _run(["partprobe"], timeout=10)


def list_media() -> list[dict[str, Any]]:
    refresh_devices()
    context = pyudev.Context()
    root_disk = _get_root_disk()
    media_list: list[dict[str, Any]] = []
    seen_devices: set[str] = set()

    def is_system_disk(disk_name: str) -> bool:
        return bool(root_disk and disk_name == root_disk)

    def add_media(
        device,
        disk_name,
        parent,
        label,
        serial,
        bus,
        fstype,
        size,
        mountpoint,
        mounted,
        *,
        bitlocker: bool = False,
        bitlocker_locked: bool = False,
    ):
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
            "bitlocker": bitlocker,
            "bitlocker_locked": bitlocker_locked,
        })

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

        add_media(
            device, disk_udev_name, parent,
            udev_part.get("ID_FS_LABEL") or udev_part.get("ID_MODEL"),
            _get_serial(parent) if parent else "INCONNU",
            (parent.get("ID_BUS") if parent else None) or "unknown",
            fstype or part.fstype, _partition_size(device), part.mountpoint, True,
        )

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

            size = _partition_size(device)
            label = part.get("ID_FS_LABEL") or part.get("ID_MODEL")
            fstype = _normalize_fstype(_get_fstype(device))

            if fstype in SUPPORTED_FS:
                add_media(device, disk_name, disk, label, serial, bus, fstype, size, None, False)
                continue

            if is_bitlocker_partition(device):
                bl_state = get_state(device)
                unlocked = bl_state["unlocked"]
                add_media(
                    device, disk_name, disk, label or "BitLocker",
                    serial, bus, "bitlocker", size,
                    bl_state["mountpoint"] if unlocked else None,
                    unlocked,
                    bitlocker=True,
                    bitlocker_locked=not unlocked,
                )

    media_list.sort(key=lambda m: (not m["mounted"], m["bitlocker_locked"], m["disk"], m["device"]))
    return media_list


def mount_readonly(device: str) -> str:
    if is_unlocked(device):
        mountpoint = get_state(device)["mountpoint"]
        if mountpoint and os.path.ismount(mountpoint):
            return mountpoint

    for part in psutil.disk_partitions():
        if part.device == device:
            return part.mountpoint

    if is_bitlocker_partition(device):
        raise RuntimeError(
            "Volume BitLocker verrouillé. Déverrouillez-le avant l'analyse."
        )

    os.makedirs(MOUNT_BASE, exist_ok=True)
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


def unmount_if_temporary(mountpoint: str, device: str | None = None) -> None:
    if mountpoint != MOUNT_BASE:
        return

    if device and is_unlocked(device):
        from bitlocker_manager import lock
        lock(device)
        return

    _run(["umount", MOUNT_BASE])
