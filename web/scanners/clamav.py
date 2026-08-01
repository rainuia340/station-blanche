"""Scanner ClamAV."""

import os
import subprocess

from scanners.base import BaseScanner, ScannerResult

QUARANTINE_DIR = "/var/lib/antivirscan/quarantine"


class ClamAVScanner(BaseScanner):
    name = "clamav"
    display_name = "ClamAV"

    def is_available(self) -> bool:
        return os.path.isfile("/usr/bin/clamscan")

    def scan(self, paths: list[str]) -> ScannerResult:
        if not self.is_available():
            return ScannerResult(
                self.name, self.display_name, -1, "", skipped=True, skip_reason="non installé"
            )

        pl = " ".join(f'"{p}"' for p in paths)
        cmd = f"/usr/bin/clamscan -r --move={QUARANTINE_DIR} --bell {pl}"
        try:
            proc = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=3600
            )
            output = proc.stdout + proc.stderr
            infected = proc.returncode == 1
            error = proc.returncode not in (0, 1) or "LibClamAV Error" in output
            return ScannerResult(
                self.name, self.display_name, proc.returncode, output,
                infected=infected, error=error,
            )
        except Exception as exc:
            return ScannerResult(
                self.name, self.display_name, -1, str(exc), error=True
            )

    def update_signatures(self) -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                ["freshclam"], capture_output=True, text=True, timeout=300
            )
            return proc.returncode == 0, proc.stdout + proc.stderr
        except Exception as exc:
            return False, str(exc)
