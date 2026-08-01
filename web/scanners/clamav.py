"""Scanner ClamAV."""

import os
import subprocess

from scanners.base import BaseScanner, ScannerResult, run_subprocess

QUARANTINE_DIR = "/var/lib/antivirscan/quarantine"
CLAMAV_UPDATE_SCRIPT = "/opt/station-blanche/scripts/clamav-update.sh"


class ClamAVScanner(BaseScanner):
    name = "clamav"
    display_name = "ClamAV"

    def is_available(self) -> bool:
        return os.path.isfile("/usr/bin/clamscan")

    def scan(self, paths, cancel_check=None, register_proc=None) -> ScannerResult:
        if not self.is_available():
            return ScannerResult(
                self.name, self.display_name, -1, "", skipped=True, skip_reason="non installé"
            )

        pl = " ".join(f'"{p}"' for p in paths)
        cmd = f"/usr/bin/clamscan -r --move={QUARANTINE_DIR} --bell {pl}"
        try:
            code, stdout, stderr, cancelled = run_subprocess(
                cmd,
                shell=True,
                cancel_check=cancel_check,
                register_proc=register_proc,
            )
            if cancelled:
                return ScannerResult(
                    self.name, self.display_name, -1, "", cancelled=True
                )
            output = stdout + stderr
            infected = code == 1
            error = code not in (0, 1) or "LibClamAV Error" in output
            return ScannerResult(
                self.name, self.display_name, code, output,
                infected=infected, error=error,
            )
        except Exception as exc:
            return ScannerResult(
                self.name, self.display_name, -1, str(exc), error=True
            )

    def update_signatures(self) -> tuple[bool, str]:
        if os.path.isfile(CLAMAV_UPDATE_SCRIPT):
            try:
                proc = subprocess.run(
                    ["bash", CLAMAV_UPDATE_SCRIPT],
                    capture_output=True,
                    text=True,
                    timeout=600,
                )
                output = proc.stdout + proc.stderr
                return proc.returncode == 0, output
            except Exception as exc:
                return False, str(exc)

        freshclam = "/usr/bin/freshclam"
        if not os.path.isfile(freshclam):
            return False, "freshclam introuvable — installez le paquet clamav-freshclam"

        try:
            subprocess.run(
                ["systemctl", "stop", "clamav-freshclam"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            code, stdout, stderr, _ = run_subprocess([freshclam, "--stdout"])
            subprocess.run(
                ["systemctl", "start", "clamav-freshclam"],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = stdout + stderr
            if code == 0:
                return True, output
            if code == 1 and (
                os.path.isfile("/var/lib/clamav/main.cvd")
                or os.path.isfile("/var/lib/clamav/main.cld")
            ):
                return True, output + "\nSignatures déjà à jour."
            return False, output
        except Exception as exc:
            return False, str(exc)
