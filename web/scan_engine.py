"""Moteur de détection USB et scan ClamAV."""

import datetime
import os
import subprocess
import threading
import time

import psutil
import pyudev

LOG_DIR = "/var/log/antivirscan"
QUARANTINE_DIR = "/var/lib/antivirscan/quarantine"

STATE_IDLE = "idle"
STATE_WAITING_USB = "waiting_usb"
STATE_SCANNING = "scanning"
STATE_INFECTED = "infected"
STATE_CLEAN = "clean"
STATE_ERROR = "error"
STATE_MULTIPLE_USB = "multiple_usb"
STATE_WAITING_EJECT = "waiting_eject"


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
    def _usb_disk_count() -> int:
        context = pyudev.Context()
        devices = context.list_devices(subsystem="block", ID_BUS="usb")
        return sum(1 for d in devices if d.get("DEVTYPE") == "disk")

    @staticmethod
    def _mounted_usb_partitions() -> list[str]:
        parts = []
        context = pyudev.Context()
        devices = context.list_devices(subsystem="block", ID_BUS="usb")
        for device in devices:
            if device.get("DEVTYPE") != "disk":
                continue
            partitions = [
                d.device_node
                for d in context.list_devices(
                    subsystem="block", DEVTYPE="partition", parent=device
                )
            ]
            for p in psutil.disk_partitions():
                if p.device in partitions:
                    parts.append(p.mountpoint)
        return parts

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
        parts = self._mounted_usb_partitions()
        if not parts:
            self._set(STATE_ERROR, "Aucune partition montée sur la clé USB.")
            return

        pl = " ".join(f'"{p}"' for p in parts)
        dt = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        log_path = f"{LOG_DIR}/scan-{dt}.log"

        with self._lock:
            self._current_log = log_path
            self._log_lines = [f"Analyse de {pl}"]

        self._set(STATE_SCANNING, "Analyse antivirus en cours...", f"Début analyse : {pl}")

        output = ""
        cmd = f"/usr/bin/clamscan -r --move={QUARANTINE_DIR} --bell {pl}"
        try:
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
            )
            for line in proc.stdout:
                output += line
                self._set(STATE_SCANNING, "Analyse antivirus en cours...", line.rstrip())
            result = proc.wait()
        except Exception as exc:
            self._set(STATE_ERROR, f"Erreur pendant l'analyse : {exc}")
            return

        with open(log_path, "w", encoding="utf-8") as f:
            f.write(output)

        if "LibClamAV Error" in output:
            result = 2

        if result == 1:
            self._set(
                STATE_INFECTED,
                "Infection détectée ! Fichiers mis en quarantaine. Réinsérez la clé pour valider la désinfection.",
            )
        elif result == 0:
            self._set(STATE_CLEAN, "Aucune infection détectée. Cette clé est saine.")
        else:
            self._set(STATE_ERROR, "Une erreur est survenue pendant l'analyse.")

        self._set(STATE_WAITING_EJECT, "Veuillez retirer la clé USB.")
