"""Scanner Linux Malware Detect (LMD / maldet)."""

import os
import subprocess

from scanners.base import BaseScanner, ScannerResult


class MaldetScanner(BaseScanner):
    name = "maldet"
    display_name = "Linux Malware Detect (LMD)"

    def is_available(self) -> bool:
        return os.path.isfile("/usr/local/sbin/maldet")

    def scan(self, paths: list[str]) -> ScannerResult:
        if not self.is_available():
            return ScannerResult(
                self.name, self.display_name, -1, "", skipped=True, skip_reason="non installé"
            )

        output_parts = []
        infected = False
        error = False
        last_code = 0

        for path in paths:
            try:
                proc = subprocess.run(
                    ["/usr/local/sbin/maldet", "-a", path],
                    capture_output=True, text=True, timeout=3600,
                )
                block = f"--- maldet -a {path} ---\n{proc.stdout}{proc.stderr}"
                output_parts.append(block)
                last_code = proc.returncode
                # maldet : 0 = propre, 1 = menace(s) détectée(s)
                if proc.returncode == 1:
                    infected = True
                elif proc.returncode not in (0, 1):
                    error = True
            except Exception as exc:
                output_parts.append(f"Erreur maldet sur {path}: {exc}")
                error = True

        return ScannerResult(
            self.name, self.display_name, last_code, "\n".join(output_parts),
            infected=infected, error=error and not infected,
        )

    def update_signatures(self) -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                ["/usr/local/sbin/maldet", "-u"],
                capture_output=True, text=True, timeout=300,
            )
            return proc.returncode == 0, proc.stdout + proc.stderr
        except Exception as exc:
            return False, str(exc)
