"""Moteur de scan multi-antivirus — sélection manuelle des médias."""

import datetime
import os
import threading
import time

from media_manager import list_media, mount_readonly, unmount_if_temporary
from scanners import ALL_SCANNERS

LOG_DIR = "/var/log/antivirscan"
QUARANTINE_DIR = "/var/lib/antivirscan/quarantine"
REPORT_DIR = "STATION_BLANCHE"

STATE_IDLE = "idle"
STATE_SCANNING = "scanning"
STATE_INFECTED = "infected"
STATE_CLEAN = "clean"
STATE_ERROR = "error"
STATE_CANCELLED = "cancelled"

RESULT_LABELS = {
    0: "SAIN — Aucune infection détectée",
    1: "INFECTE — Menace(s) détectée(s)",
    2: "ERREUR — Analyse incomplète",
    3: "ANNULE — Analyse interrompue par l'utilisateur",
}

PROGRESS_MOUNT = 10
PROGRESS_FINALIZE = 95


class ScanEngine:
    def __init__(self):
        self._lock = threading.Lock()
        self._state = STATE_IDLE
        self._message = "Sélectionnez un média et lancez l'analyse."
        self._log_lines: list[str] = []
        self._current_log = ""
        self._current_scanner = ""
        self._media_list: list[dict] = []
        self._scan_thread: threading.Thread | None = None
        self._progress = 0
        self._progress_label = ""
        self._cancel_requested = False
        self._current_proc = None

    def start(self):
        os.makedirs(LOG_DIR, exist_ok=True)
        os.makedirs(QUARANTINE_DIR, exist_ok=True)
        self.refresh_media()

    def stop(self):
        pass

    def refresh_media(self) -> list[dict]:
        try:
            media = list_media()
            with self._lock:
                self._media_list = media
            return media
        except Exception as exc:
            with self._lock:
                self._media_list = []
            raise exc

    def status(self) -> dict:
        with self._lock:
            return {
                "state": self._state,
                "message": self._message,
                "log": self._log_lines[-120:],
                "log_file": self._current_log,
                "current_scanner": self._current_scanner,
                "media": self._media_list,
                "scanning": self._state == STATE_SCANNING,
                "progress": self._progress,
                "progress_label": self._progress_label,
            }

    def _set(
        self,
        state: str,
        message: str,
        log_line: str | None = None,
        scanner: str | None = None,
        progress: int | None = None,
        progress_label: str | None = None,
    ):
        with self._lock:
            self._state = state
            self._message = message
            if scanner is not None:
                self._current_scanner = scanner
            if log_line:
                self._log_lines.append(log_line)
            if progress is not None:
                self._progress = max(0, min(100, progress))
            if progress_label is not None:
                self._progress_label = progress_label

    def _is_cancelled(self) -> bool:
        with self._lock:
            return self._cancel_requested

    def _register_proc(self, proc):
        with self._lock:
            self._current_proc = proc

    def cancel_scan(self) -> tuple[bool, str]:
        with self._lock:
            if self._state != STATE_SCANNING:
                return False, "Aucune analyse en cours."
            self._cancel_requested = True
            proc = self._current_proc
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        return True, "Annulation en cours..."

    def start_scan(self, device: str) -> tuple[bool, str]:
        with self._lock:
            if self._state == STATE_SCANNING:
                return False, "Une analyse est déjà en cours."

        media = next((m for m in self._media_list if m["device"] == device), None)
        if not media:
            return False, "Média introuvable. Actualisez la liste."

        with self._lock:
            self._cancel_requested = False
            self._progress = 0
            self._progress_label = "Préparation..."

        self._scan_thread = threading.Thread(
            target=self._run_scan, args=(media,), daemon=True
        )
        self._scan_thread.start()
        return True, "Analyse démarrée."

    @staticmethod
    def _build_log_filename(serial: str, device_id: str) -> tuple[str, str]:
        now = datetime.datetime.now()
        safe_id = device_id.replace("/", "_")
        filename = f"{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S')}-{serial}-{safe_id}.log"
        return filename, now.strftime("%d/%m/%Y %H:%M:%S")

    @staticmethod
    def _build_report_header(
        timestamp: str, media: dict, mount_point: str, scanner_results: list, overall: int
    ) -> str:
        lines = [
            "=" * 60,
            "  STATION BLANCHE — Rapport d'analyse multi-antivirus",
            "=" * 60,
            f"Date et heure    : {timestamp}",
            f"Périphérique     : {media['device']}",
            f"Label            : {media['label']}",
            f"N° série         : {media['serial']}",
            f"Système fichiers : {media['fstype']}",
            f"Point de montage : {mount_point}",
            f"Moteurs actifs   : {len([r for r in scanner_results if not r.skipped])}",
            "",
            "Résultats par moteur :",
        ]
        for r in scanner_results:
            lines.append(f"  - {r.display_name:<30} {r.status_label}")
        lines.extend([
            "",
            f"Résultat global  : {RESULT_LABELS.get(overall, 'INCONNU')}",
            "=" * 60,
            "",
        ])
        return "\n".join(lines)

    @staticmethod
    def _copy_report(log_path: str, mount_point: str, filename: str) -> bool:
        import shutil
        try:
            dest_dir = os.path.join(mount_point, REPORT_DIR)
            os.makedirs(dest_dir, exist_ok=True)
            shutil.copy2(log_path, os.path.join(dest_dir, filename))
            return True
        except OSError:
            return False

    def _scanner_progress(self, index: int, total: int) -> int:
        if total <= 0:
            return PROGRESS_MOUNT
        span = PROGRESS_FINALIZE - PROGRESS_MOUNT
        return PROGRESS_MOUNT + int(span * (index + 1) / total)

    def _run_scan(self, media: dict):
        device = media["device"]
        mount_point = None
        temp_mount = False
        scanner_count = len(ALL_SCANNERS)

        filename, timestamp = self._build_log_filename(media["serial"], media["id"])
        log_path = os.path.join(LOG_DIR, filename)

        with self._lock:
            self._current_log = log_path
            self._log_lines = [
                f"Média : {media['label']} ({device})",
                f"Système de fichiers : {media['fstype']}",
                f"Fichier log : {filename}",
                "",
            ]

        self._set(
            STATE_SCANNING,
            f"Montage de {media['label']}...",
            progress=2,
            progress_label="Montage du média",
        )

        if self._is_cancelled():
            self._finish_cancelled(temp_mount, mount_point)
            return

        try:
            if media["mounted"] and media["mountpoint"]:
                mount_point = media["mountpoint"]
                self._set(
                    STATE_SCANNING,
                    f"Utilisation du montage existant : {mount_point}",
                    progress=PROGRESS_MOUNT,
                    progress_label="Média prêt",
                )
            else:
                self._set(STATE_SCANNING, f"Montage de {device} en lecture seule...")
                mount_point = mount_readonly(device)
                temp_mount = True
                self._set(
                    STATE_SCANNING,
                    f"Monté sur {mount_point}",
                    f"Montage réussi : {mount_point}",
                    progress=PROGRESS_MOUNT,
                    progress_label="Média monté",
                )
        except Exception as exc:
            self._set(STATE_ERROR, f"Erreur de montage : {exc}", str(exc), progress=0, progress_label="")
            return

        if self._is_cancelled():
            self._finish_cancelled(temp_mount, mount_point)
            return

        parts = [mount_point]
        scanner_results = []
        full_output = ""
        any_infected = False
        any_success = False
        all_failed = True
        cancelled = False

        for index, scanner in enumerate(ALL_SCANNERS):
            if self._is_cancelled():
                cancelled = True
                break

            progress = self._scanner_progress(index, scanner_count)
            progress_label = f"Moteur {index + 1}/{scanner_count} : {scanner.display_name}"

            if not scanner.is_available():
                result = scanner.scan(parts)
                scanner_results.append(result)
                self._set(
                    STATE_SCANNING,
                    f"Analyse en cours — {media['label']}",
                    f"[{scanner.display_name}] ignoré — non installé",
                    scanner=scanner.display_name,
                    progress=progress,
                    progress_label=progress_label,
                )
                continue

            self._set(
                STATE_SCANNING,
                f"{scanner.display_name} — {media['label']}",
                f"--- {scanner.display_name} ---",
                scanner=scanner.display_name,
                progress=progress,
                progress_label=progress_label,
            )

            result = scanner.scan(
                parts,
                cancel_check=self._is_cancelled,
                register_proc=self._register_proc,
            )
            scanner_results.append(result)
            full_output += f"\n{'=' * 40}\n{scanner.display_name}\n{'=' * 40}\n{result.output}\n"

            for line in result.output.splitlines()[-15:]:
                if line.strip():
                    self._set(STATE_SCANNING, f"{scanner.display_name} en cours...", line.rstrip())

            if result.cancelled:
                cancelled = True
                self._set(
                    STATE_SCANNING,
                    "Annulation...",
                    f"[{scanner.display_name}] analyse interrompue",
                    progress=progress,
                    progress_label="Annulation",
                )
                break

            if not result.skipped and not result.error:
                any_success = True
                all_failed = False
            if result.infected:
                any_infected = True
            if not result.skipped:
                all_failed = all_failed and result.error

        if cancelled:
            report = self._build_report_header(timestamp, media, mount_point, scanner_results, 3)
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(report + full_output + "\nAnalyse annulée par l'utilisateur.\n")
            self._finish_cancelled(temp_mount, mount_point, filename)
            return

        if any_infected:
            overall = 1
        elif all_failed or not any_success:
            overall = 2
        else:
            overall = 0

        self._set(
            STATE_SCANNING,
            "Finalisation du rapport...",
            progress=PROGRESS_FINALIZE,
            progress_label="Génération du rapport",
        )

        report = self._build_report_header(timestamp, media, mount_point, scanner_results, overall)
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(report + full_output)

        if self._copy_report(log_path, mount_point, filename):
            self._set(STATE_SCANNING, "Finalisation...", f"Rapport copié : {REPORT_DIR}/{filename}")

        if temp_mount:
            unmount_if_temporary(mount_point)

        self._set(progress=100, progress_label="Terminé")

        if overall == 1:
            self._set(STATE_INFECTED, "Infection détectée ! Fichiers mis en quarantaine.", f"Log : {filename}")
        elif overall == 0:
            self._set(STATE_CLEAN, "Aucune infection détectée. Ce média est sain.", f"Log : {filename}")
        else:
            self._set(STATE_ERROR, "Une erreur est survenue pendant l'analyse.", f"Log : {filename}")

        self._set(
            STATE_IDLE,
            "Analyse terminée. Vous pouvez actualiser la liste ou analyser un autre média.",
            scanner="",
            progress=0,
            progress_label="",
        )
        time.sleep(0.5)
        try:
            self.refresh_media()
        except Exception:
            pass

    def _finish_cancelled(self, temp_mount: bool, mount_point: str | None, filename: str = ""):
        if temp_mount and mount_point:
            unmount_if_temporary(mount_point)
        log_msg = f"Log partiel : {filename}" if filename else "Analyse interrompue."
        self._set(
            STATE_CANCELLED,
            "Analyse annulée.",
            log_msg,
            scanner="",
            progress=0,
            progress_label="",
        )
        with self._lock:
            self._cancel_requested = False
        time.sleep(1.5)
        self._set(
            STATE_IDLE,
            "Sélectionnez un média et lancez l'analyse.",
            progress=0,
            progress_label="",
        )
        try:
            self.refresh_media()
        except Exception:
            pass
