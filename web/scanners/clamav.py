"""Scanner ClamAV."""

import os

from scanners.base import BaseScanner, ScannerResult, run_subprocess

QUARANTINE_DIR = "/var/lib/antivirscan/quarantine"


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
        try:
            code, stdout, stderr, _ = run_subprocess(["freshclam"])
            return code == 0, stdout + stderr
        except Exception as exc:
            return False, str(exc)
