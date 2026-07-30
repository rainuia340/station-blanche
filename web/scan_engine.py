"""Moteur de détection USB et scan ClamAV."""

import datetime
import os
import re
import shutil
import subprocess
import threading
import time

import psutil
import pyudev

LOG_DIR = "/var/log/antivirscan"
QUARANTINE_DIR = "/var/lib/antivirscan/quarantine"
USB_REPORT_DIR = "STATION_BLANCHE"

STATE_IDLE = "idle"
STATE_WAITING_USB = "waiting_usb"
STATE_SCANNING = "scanning"
STATE_INFECTED = "infected"
STATE_CLEAN = "clean"
STATE_ERROR = "error"
STATE_MULTIPLE_USB = "multiple_usb"
STATE_WAITING_EJECT = "waiting_eject"

RESULT_LABELS = {
    0: "SAIN — Aucune infection détectée",
    1: "INFECTE — Fichiers mis en quarantaine",
    2: "ERREUR — Analyse incomplète",
}


def sanitize_serial(serial: str) -> str:
    cleaned = re.sub(r"[^\w\-]", "_", serial.strip())
    return cleaned[:64] if cleaned else "INCONNU"


class ScanEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = STATE_WAITING_USB
        self._message = "Insérez une clé USB pour commencer l'analyse."
        self._log_lines: list[str] = []
        self._current_log = ""
        self._thread: threading.Thread | None = None
        self._running = False

    def start(self):
        if self._running:
            return
        self._running = True
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(QUARANTINE_DIR, exist_ok=True)
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "message": self._message,
                "log": self._log_lines[-80:],
                "log_file": self._current_log,
            }

    def _set(self, state: str, message: str, log_line: str | None = None):
        with self._lock:
            self._state = state
            self._message = message
            if log_line:
                self._log_lines.append(log_line)

    @staticmethod
    def _usb_disks() -> list:
        context = pyudev.Context()
        return [
            d for d in context.list_devices(subsystem="block", ID_BUS="usb")
            if d.get("DEVTYPE") == "disk"
        ]

    @staticmethod
    def _usb_disk_count() -> int:
        return len(ScanEngine._usb_disks())

    @staticmethod
    def _get_usb_serial(disk) -> str:
        serial = (
            disk.get("ID_SERIAL_SHORT")
            or disk.get("ID_SERIAL")
            or disk.get("ID_USB_SERIAL_NUM")
            or disk.get("ID_MODEL")
            or "INCONNU"
        )
        return sanitize_serial(serial)

    @staticmethod
    def _mounted_usb_partitions() -> tuple[list[str], str]:
        """Retourne (points de montage, numéro de série)."""
        parts = []
        serial = "INCONNU"
        context = pyudev.Context()
        disks = ScanEngine._usb_disks()

        if len(disks) == 1:
            serial = ScanEngine._get_usb_serial(disks[0])

        for disk in disks:
            partitions = [
                d.device_node
                for d in context.list_devices(
                    subsystem="block", DEVTYPE="partition", parent=disk
                )
            ]
            for p in psutil.disk_partitions():
                if p.device in partitions:
                    parts.append(p.mountpoint)

        return parts, serial

    @staticmethod
    def _build_log_filename(serial: str) -> tuple[str, str]:
        now = datetime.datetime.now()
        date_part = now.strftime("%Y%m%d")
        time_part = now.strftime("%H%M%S")
        filename = f"{date_part}-{time_part}-{serial}.log"
        return filename, now.strftime("%d/%m/%Y %H:%M:%S")

    @staticmethod
    def _build_report_header(
        timestamp: str, serial: str, mount_points: list[str], result: int
    ) -> str:
        lines = [
            "=" * 60,
            "  STATION BLANCHE — Rapport d'analyse antivirus",
            "=" * 60,
            f"Date et heure    : {timestamp}",
            f"N° série clé USB : {serial}",
            f"Partitions       : {', '.join(mount_points)}",
            f"Résultat         : {RESULT_LABELS.get(result, 'INCONNU')}",
            "=" * 60,
            "",
        ]
        return "\n".join(lines)

    @staticmethod
    def _copy_log_to_usb(log_path: str, mount_points: list[str], filename: str) -> list[str]:
        copied = []
        for mp in mount_points:
            try:
                dest_dir = os.path.join(mp, USB_REPORT_DIR)
                os.makedirs(dest_dir, exist_ok=True)
                dest = os.path.join(dest_dir, filename)
                shutil.copy2(log_path, dest)
                copied.append(dest)
            except OSError as exc:
                print(f"[scan] Impossible de copier sur {mp}: {exc}")
        return copied

    def _loop(self):
        self._set(STATE_WAITING_USB, "Insérez une clé USB pour commencer l'analyse.")
        while self._running:
            time.sleep(1)
            count = self._usb_disk_count()
            if count == 0:
                if self._state == STATE_WAITING_EJECT:
                    self._set(
                        STATE_WAITING_USB,
                        "Insérez une clé USB pour commencer l'analyse.",
                        "Clé retirée. En attente d'un nouveau média.",
                    )
                continue
            if count > 1:
                self._set(
                    STATE_MULTIPLE_USB,
                    "Plusieurs clés détectées. Ne branchez qu'un seul média à la fois.",
                )
                continue
            if self._state in (STATE_WAITING_USB, STATE_CLEAN, STATE_INFECTED, STATE_ERROR):
                self._set(STATE_SCANNING, "Clé USB détectée. Montage en cours...")
                time.sleep(8)
                self._run_scan()

    def _run_scan(self):
        parts, serial = self._mounted_usb_partitions()
        if not parts:
            self._set(STATE_ERROR, "Aucune partition montée sur la clé USB.")
            return

        filename, timestamp = self._build_log_filename(serial)
        log_path = os.path.join(LOG_DIR, filename)

        with self._lock:
            self._current_log = log_path
            self._log_lines = [
                f"Clé USB détectée — N° série : {serial}",
                f"Fichier log : {filename}",
            ]

        self._set(
            STATE_SCANNING,
            f"Analyse en cours (série : {serial})...",
            f"Début analyse : {', '.join(parts)}",
        )

        output = ""
        pl = " ".join(f'"{p}"' for p in parts)
        cmd = f"/usr/bin/clamscan -r --move={QUARANTINE_DIR} --bell {pl}"
        try:
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                output += line
                self._set(STATE_SCANNING, f"Analyse en cours (série : {serial})...", line.rstrip())
            result = proc.wait()
        except Exception as exc:
            self._set(STATE_ERROR, f"Erreur pendant l'analyse : {exc}")
            return

        if "LibClamAV Error" in output:
            result = 2

        report = self._build_report_header(timestamp, serial, parts, result)
        full_content = report + output

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(full_content)

        copied = self._copy_log_to_usb(log_path, parts, filename)
        if copied:
            self._set(
                STATE_SCANNING,
                f"Analyse en cours (série : {serial})...",
                f"Rapport copié sur la clé : {USB_REPORT_DIR}/{filename}",
            )

        if result == 1:
            self._set(
                STATE_INFECTED,
                "Infection détectée ! Fichiers mis en quarantaine. Réinsérez la clé pour valider la désinfection.",
                f"Log : {filename}",
            )
        elif result == 0:
            self._set(
                STATE_CLEAN,
                "Aucune infection détectée. Cette clé est saine.",
                f"Log : {filename}",
            )
        else:
            self._set(
                STATE_ERROR,
                "Une erreur est survenue pendant l'analyse.",
                f"Log : {filename}",
            )

        self._set(STATE_WAITING_EJECT, "Veuillez retirer la clé USB.")
